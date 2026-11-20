import { cookies, headers } from 'next/headers';
import { cache } from 'react';
import { fetchGardenMe, fetchMe } from './api';
import { getAuth } from './auth';
import { isUnauthorized, logAuthError } from './auth-log';
import type { Garden, User } from './types';

// 求職者のログインの印は、Better Auth の Cookie（HttpOnly。画面のサーバーだけが読む。lib/auth.ts）。API へは、そこから取る短命の JWT を渡す。
// 園のログインは別の仕組み（API のセッション）で、Cookie も別の名前なので、同じブラウザーで両方にログインしても混ざらない。
export const GARDEN_SESSION_COOKIE = 'hj_garden_session';

const SESSION_SECONDS = 60 * 60 * 24 * 14; // API の SESSION_DAYS と同じ

async function setToken(name: string, token: string): Promise<void> {
  (await cookies()).set(name, token, {
    httpOnly: true,
    sameSite: 'lax',
    path: '/',
    maxAge: SESSION_SECONDS,
    // https で公開するときは SESSION_COOKIE_SECURE=true にする（ローカルの http では付けない）
    secure: process.env.SESSION_COOKIE_SECURE === 'true',
  });
}

export const setGardenSessionCookie = (token: string) => setToken(GARDEN_SESSION_COOKIE, token);

/** ログイン中の求職者の JWT（API へ Bearer で渡す。15 分。ログインしていない・設定が無い・取れないときは null）。同じ描画の中では 1 回しか取らない。 */
export const userToken = cache(async (): Promise<string | null> => {
  const auth = getAuth();
  if (!auth) return null;
  try {
    return (await auth.api.getToken({ headers: await headers() }))?.token ?? null;
  } catch (error) {
    // ログインしていない（401）は普通の状態なので記録しない。それ以外は画面では「ログアウト」に見える。
    // 原因（migrate の前に使った・BETTER_AUTH_SECRET を変えた）は、ここにしか残らない
    if (!isUnauthorized(error)) logAuthError('userToken', error);
    return null;
  }
});

/** ログイン中の利用者。ログインしていない・期限切れ・API に届かないときは null。同じ描画の中では 1 回しか呼ばない。 */
export const currentUser = cache(async (): Promise<User | null> => {
  const token = await userToken();
  if (!token) return null;
  try {
    return await fetchMe(token);
  } catch {
    return null;
  }
});

/** 園のトークン（Cookie）。無ければ undefined。 */
export async function gardenToken(): Promise<string | undefined> {
  return (await cookies()).get(GARDEN_SESSION_COOKIE)?.value;
}

/** ログイン中の園。Cookie が無い・期限切れ・API に届かないときは null。同じ描画の中では 1 回しか呼ばない。 */
export const currentGarden = cache(async (): Promise<Garden | null> => {
  const token = await gardenToken();
  if (!token) return null;
  try {
    return await fetchGardenMe(token);
  } catch {
    return null;
  }
});

export function displayName(user: Pick<User, 'last_name' | 'first_name' | 'email'>): string {
  return [user.last_name, user.first_name].filter(Boolean).join(' ') || user.email;
}
