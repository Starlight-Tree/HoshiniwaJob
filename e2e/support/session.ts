// Better Auth のログイン済みの状態を、使い捨てスタックに作る（本物の Google へは自動でログインできないため）。
// 作るもの: DB の行（auth_user・auth_session）と、署名つきの Cookie。Better Auth はテスト側に入れず、Node 標準の crypto と pg だけを使う。
//
// 注意: Cookie の署名の作り方（HMAC-SHA256 を標準の base64 にして `<token>.<署名>` を URL エンコード）は、Better Auth 1.7.18 の挙動の写し。
// frontend/package.json の better-auth の版を上げたら、この写しが今の版と合っているか、必ず確かめ直す（合わなければ、`assertSessionSynced` が原因を示して落ちる）。
import { createHmac, randomBytes } from 'node:crypto';
import type { BrowserContext, Page } from '@playwright/test';
import pg from 'pg';

/** frontend/src/lib/auth-config.ts の AUTH_COOKIE_PREFIX。http のオリジンなので `__Secure-` は付かない（https の経路は、この E2E では確かめない） */
export const SESSION_COOKIE_NAME = 'jobnavi.session_token';

export const E2E_USER = {
  id: 'e2e-user-0001', // JWT の sub の形式 [A-Za-z0-9_-]{8,64}
  name: 'E2E 太郎',
  email: 'e2e-user@example.test',
} as const;

export function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} が未設定です（e2e/run.sh から流してください）`);
  return value;
}

/** DB 名が `_e2e` で終わらなければ例外（開発 DB に書かないための安全確認）。接続文字列は、例外に含めない。 */
export function assertE2eDatabase(connectionString: string): void {
  let name = '';
  try {
    name = decodeURIComponent(new URL(connectionString).pathname.replace(/^\//, ''));
  } catch {
    throw new Error('E2E_DATABASE_URL を URL として読めません');
  }
  if (!name.endsWith('_e2e')) throw new Error('E2E_DATABASE_URL の DB 名が _e2e で終わっていないので、何も書きません');
}

/** Cookie の値（URL エンコード済み）。Better Auth の署名つき Cookie と同じ形。 */
export function signCookieValue(token: string, secret: string): string {
  const signature = createHmac('sha256', Buffer.from(secret, 'utf8')).update(token).digest('base64');
  return encodeURIComponent(`${token}.${signature}`);
}

/** 乱数の秘密（署名が検査されているかの対照に使う） */
export function randomSecret(): string {
  return randomBytes(32).toString('hex');
}

/** この DB に、テスト用の利用者とセッションを入れて、セッションの token を返す。何度流しても同じ状態から始まる。 */
export async function seedSession(connectionString = requiredEnv('E2E_DATABASE_URL')): Promise<string> {
  assertE2eDatabase(connectionString);
  const token = randomBytes(24).toString('base64url'); // 32 文字（英数字と _ -）
  const client = new pg.Client({ connectionString });
  await client.connect();
  try {
    await client.query('BEGIN');
    // API のプロフィール（users）の e2e 用の行は、あれば先に消す（前の実行の表示名を持ち越さない）
    await client.query('DELETE FROM users WHERE auth_user_id = $1 OR lower(email) = $2', [E2E_USER.id, E2E_USER.email]);
    await client.query(
      `INSERT INTO auth_user ("id", "name", "email", "emailVerified")
       VALUES ($1, $2, $3, true)
       ON CONFLICT ("id") DO UPDATE SET "name" = EXCLUDED."name", "email" = EXCLUDED."email", "emailVerified" = true, "updatedAt" = now()`,
      [E2E_USER.id, E2E_USER.name, E2E_USER.email],
    );
    // 以前のセッションは消す（token は毎回新しい）。"updatedAt" は NOT NULL で DEFAULT が無いので、必ず入れる
    await client.query('DELETE FROM auth_session WHERE "userId" = $1', [E2E_USER.id]);
    await client.query(
      `INSERT INTO auth_session ("id", "token", "expiresAt", "createdAt", "updatedAt", "userId")
       VALUES ($1, $2, now() + interval '1 day', now(), now(), $3)
       ON CONFLICT ("id") DO UPDATE SET "token" = EXCLUDED."token", "expiresAt" = EXCLUDED."expiresAt", "updatedAt" = now(), "userId" = EXCLUDED."userId"`,
      [`e2e-session-${randomBytes(6).toString('hex')}`, token, E2E_USER.id],
    );
    await client.query('COMMIT');
  } catch (error) {
    await client.query('ROLLBACK').catch(() => undefined);
    throw error;
  } finally {
    await client.end();
  }
  return token;
}

/** JWKS の鍵を先に 1 つ作らせる（最初のログインで、画面（getToken）と API の JWKS 取得が同時に鍵を作って、2 つできるのを避ける。推測に基づく予防） */
export async function warmJwks(page: Page): Promise<void> {
  const response = await page.request.get('/api/auth/jwks');
  if (!response.ok()) throw new Error(`/api/auth/jwks が ${response.status()} を返しました`);
  const body = (await response.json()) as { keys?: unknown[] };
  if (!Array.isArray(body.keys) || body.keys.length === 0) throw new Error('/api/auth/jwks に鍵がありません');
}

/** Cookie を入れる（署名の秘密は引数。正しい値は E2E_BETTER_AUTH_SECRET） */
export async function injectSessionCookie(context: BrowserContext, token: string, secret: string): Promise<void> {
  await context.addCookies([
    {
      name: SESSION_COOKIE_NAME,
      value: signCookieValue(token, secret),
      url: requiredEnv('E2E_ORIGIN'),
      httpOnly: true,
      sameSite: 'Lax',
      expires: Math.floor(Date.now() / 1000) + 60 * 60,
    },
  ]);
}

/** 注入が画面のサーバー（Better Auth）に通ったかを確かめる。形式が変わったときの、原因の切り分け用。 */
export async function assertSessionSynced(page: Page): Promise<void> {
  const response = await page.request.get('/api/auth/get-session');
  const body = (await response.json().catch(() => null)) as { user?: { email?: string } } | null;
  if (body?.user?.email !== E2E_USER.email) {
    throw new Error(
      '注入したセッションを Better Auth が認めませんでした（Cookie の名前・署名の形式・auth_session の列が、Better Auth の版と合っているか確かめてください）',
    );
  }
}

/** ログイン済みの状態にする（DB・Cookie・同期の確認）。ページを開く前に呼ぶ。 */
export async function signIn(page: Page): Promise<void> {
  await warmJwks(page);
  const token = await seedSession();
  await injectSessionCookie(page.context(), token, requiredEnv('E2E_BETTER_AUTH_SECRET'));
  await assertSessionSynced(page);
}

/** 別の秘密で署名した Cookie を入れる（DB には正しいセッションがある）。署名が検査されていれば、ログインしていない扱いになる。 */
export async function signInWithWrongSignature(page: Page): Promise<void> {
  await warmJwks(page);
  const token = await seedSession();
  await injectSessionCookie(page.context(), token, randomSecret());
}
