import { createHash, randomBytes, timingSafeEqual } from 'node:crypto';

// Google でのログインのうち、画面のサーバーが受け持つ部分（Google の同意画面へ送り出す・戻ってきたときの照合）。サーバー側だけで使う。
// コードの交換・ID トークンの検証・利用者の紐づけは API（backend/app/google_login.py）。クライアントのシークレットは、画面のサーバーにも渡さない。
// state（CSRF の対策）・nonce（ID トークンの使い回しの対策）・PKCE の verifier は、このサーバーが作り、HttpOnly の Cookie に 10 分だけ持つ。

export const OAUTH_COOKIE = 'hj_oauth';
export const OAUTH_COOKIE_PATH = '/auth/google';
export const OAUTH_SECONDS = 600;
const AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth';
const DEFAULT_REDIRECT = 'http://localhost:3200/auth/google/callback';

export type OAuthState = { state: string; nonce: string; verifier: string };

export function newOAuthState(): OAuthState {
  // verifier は 43〜128 文字（RFC 7636）。64 バイトの base64url は 86 文字
  return { state: randomBytes(32).toString('base64url'), nonce: randomBytes(32).toString('base64url'), verifier: randomBytes(64).toString('base64url') };
}

export const challengeOf = (verifier: string): string => createHash('sha256').update(verifier).digest('base64url');

/** Cookie に入れた値を、読み直して形を確かめる。壊れていたら null。 */
export function parseOAuthState(raw: string | undefined): OAuthState | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as Partial<OAuthState>;
    return typeof v.state === 'string' && typeof v.nonce === 'string' && typeof v.verifier === 'string' ? { state: v.state, nonce: v.nonce, verifier: v.verifier } : null;
  } catch {
    return null;
  }
}

/** 文字列が同じかを、時間から中身を読まれない形で比べる。 */
export function sameValue(a: string, b: string): boolean {
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

/** クライアント ID（公開してよい値）と、戻り先。ID が無ければ null（Google ログインは使えない）。戻り先は API の GOOGLE_REDIRECT_URI と同じ値にする。 */
export function googleConfig(): { clientId: string; redirectUri: string } | null {
  const clientId = (process.env.GOOGLE_CLIENT_ID ?? '').trim();
  if (!clientId) return null;
  // 空文字（Compose の ${VAR:-} など）も「未設定」として、既定値にする
  return { clientId, redirectUri: (process.env.GOOGLE_REDIRECT_URI ?? '').trim() || DEFAULT_REDIRECT };
}

export function authorizationUrl(config: { clientId: string; redirectUri: string }, s: OAuthState): string {
  const q = new URLSearchParams({
    client_id: config.clientId,
    redirect_uri: config.redirectUri,
    response_type: 'code',
    scope: 'openid email profile',
    state: s.state,
    nonce: s.nonce,
    code_challenge: challengeOf(s.verifier),
    code_challenge_method: 'S256',
    prompt: 'select_account',
  });
  return `${AUTH_URL}?${q}`;
}

// ログイン画面に出す文。URL には、この名前（コード）だけを入れ、文はここで決める（URL の文字をそのまま画面に出さない）。
const MESSAGES = {
  google_unconfigured: 'Google でのログインは、まだ設定されていません',
  google_failed: 'Google でのログインに失敗しました。もう一度お試しください',
  google_conflict: 'このメールアドレスは、別の Google アカウントで使われています',
} as const;

export type GoogleErrorCode = keyof typeof MESSAGES;

// Object.hasOwn: 'constructor' のような、プロトタイプにある名前を通さない
export const googleErrorMessage = (code: string | undefined): string | null => (code && Object.hasOwn(MESSAGES, code) ? MESSAGES[code as GoogleErrorCode] : null);

/** API の応答の状態から、ログイン画面に渡すコードを決める。 */
export function googleErrorCodeFor(status: number): GoogleErrorCode {
  if (status === 503) return 'google_unconfigured';
  if (status === 409) return 'google_conflict';
  return 'google_failed';
}
