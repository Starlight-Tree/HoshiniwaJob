import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { authorizationUrl, googleConfig, newOAuthState, OAUTH_COOKIE, OAUTH_COOKIE_PATH, OAUTH_SECONDS } from '../../../../src/lib/google';

export const dynamic = 'force-dynamic';

// 「Google でログイン」の入口。state・nonce・PKCE を作って Cookie に持ち、Google の同意画面へ送り出す。
// リンクは、先読み（prefetch）されないよう、next/link ではなく普通の <a> で張る。
export async function GET(): Promise<never> {
  const config = googleConfig();
  if (!config) redirect('/login?error=google_unconfigured');
  const s = newOAuthState();
  (await cookies()).set(OAUTH_COOKIE, JSON.stringify(s), {
    httpOnly: true,
    sameSite: 'lax', // Google から戻ってくる（外からの GET）ときに、Cookie が付くように
    path: OAUTH_COOKIE_PATH,
    maxAge: OAUTH_SECONDS,
    secure: process.env.SESSION_COOKIE_SECURE === 'true',
  });
  redirect(authorizationUrl(config, s));
}
