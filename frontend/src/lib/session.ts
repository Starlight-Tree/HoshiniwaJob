import { cookies } from 'next/headers';
import { cache } from 'react';
import { fetchGardenMe, fetchMe } from './api';
import type { Garden, User } from './types';

// ログインの印（トークン）は、HttpOnly の Cookie に入れ、画面のサーバーだけが読む。ブラウザーの JavaScript には見えない。
export const SESSION_COOKIE = 'hj_session';
// 園のログインの印。利用者の Cookie とは別の名前なので、同じブラウザーで両方にログインしても混ざらない
export const GARDEN_SESSION_COOKIE = 'hj_garden_session';
// 登録直後に 1 回だけ「完了しました」を出すための短い印（60 秒で消える。画面が読んだらすぐ消す）
export const REGISTERED_COOKIE = 'hj_registered';

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

export const setSessionCookie = (token: string) => setToken(SESSION_COOKIE, token);
export const setGardenSessionCookie = (token: string) => setToken(GARDEN_SESSION_COOKIE, token);

export async function setRegisteredFlag(): Promise<void> {
  (await cookies()).set(REGISTERED_COOKIE, '1', { path: '/', maxAge: 60, sameSite: 'lax' });
}

/** ログイン中の利用者。Cookie が無い・期限切れ・API に届かないときは null。同じ描画の中では 1 回しか呼ばない。 */
export const currentUser = cache(async (): Promise<User | null> => {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
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
