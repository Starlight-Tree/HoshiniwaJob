import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { ApiError, googleLoginRequest } from '../../../../src/lib/api';
import { googleConfig, googleErrorCodeFor, OAUTH_COOKIE, OAUTH_COOKIE_PATH, parseOAuthState, sameValue } from '../../../../src/lib/google';
import { setSessionCookie } from '../../../../src/lib/session';

export const dynamic = 'force-dynamic';

// Google から戻ってくる先。state を Cookie と照合し、code を API に渡してログインの印（トークン）を受け取り、HttpOnly の Cookie に入れる。
// 失敗の理由は、URL に名前（コード）だけで渡す（文はログイン画面が決める。Google や API の本文は出さない）。
export async function GET(request: Request): Promise<never> {
  const params = new URL(request.url).searchParams;
  const code = params.get('code');
  const state = params.get('state');
  const store = await cookies();
  const saved = parseOAuthState(store.get(OAUTH_COOKIE)?.value);
  store.delete({ name: OAUTH_COOKIE, path: OAUTH_COOKIE_PATH }); // 1 回だけ使う
  const config = googleConfig();
  if (!config) redirect('/login?error=google_unconfigured');
  if (params.get('error') || !code || !state || !saved || !sameValue(state, saved.state)) redirect('/login?error=google_failed');

  let token: string | null = null;
  let failure = 'google_failed';
  try {
    token = (await googleLoginRequest({ code, code_verifier: saved.verifier, nonce: saved.nonce, redirect_uri: config.redirectUri })).token;
  } catch (e) {
    failure = e instanceof ApiError ? googleErrorCodeFor(e.status) : 'google_failed';
  }
  if (!token) redirect(`/login?error=${failure}`); // redirect は例外で抜けるので、try の外で呼ぶ
  await setSessionCookie(token);
  redirect('/');
}
