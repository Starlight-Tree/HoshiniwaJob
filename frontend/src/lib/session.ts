import { cookies } from 'next/headers';
import { cache } from 'react';
import { fetchMe } from './api';
import type { User } from './types';

// ログインの印（トークン）は、HttpOnly の Cookie に入れ、画面のサーバーだけが読む。ブラウザーの JavaScript には見えない。
export const SESSION_COOKIE = 'hj_session';
// 登録直後に 1 回だけ「完了しました」を出すための短い印（60 秒で消える。画面が読んだらすぐ消す）
export const REGISTERED_COOKIE = 'hj_registered';

const SESSION_SECONDS = 60 * 60 * 24 * 14; // API の SESSION_DAYS と同じ

export async function setSessionCookie(token: string): Promise<void> {
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: 'lax',
    path: '/',
    maxAge: SESSION_SECONDS,
    // https で公開するときは SESSION_COOKIE_SECURE=true にする（ローカルの http では付けない）
    secure: process.env.SESSION_COOKIE_SECURE === 'true',
  });
}

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

export function displayName(user: Pick<User, 'last_name' | 'first_name' | 'email'>): string {
  return [user.last_name, user.first_name].filter(Boolean).join(' ') || user.email;
}
