'use server';

import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { gardenLoginRequest, gardenLogoutRequest } from '../lib/api';
import { messageFor } from '../lib/error-message';
import type { FormState } from '../lib/form-state';
import { GARDEN_SESSION_COOKIE, setGardenSessionCookie } from '../lib/session';
import { validateLogin } from '../lib/validation';

const text = (data: FormData, key: string) => String(data.get(key) ?? '');

export async function gardenLoginAction(_prev: FormState, data: FormData): Promise<FormState> {
  const email = text(data, 'email').trim();
  const password = text(data, 'password');
  const fieldErrors = validateLogin({ email, password });
  if (Object.keys(fieldErrors).length > 0) return { fieldErrors, values: { email } };

  let token: string;
  try {
    token = (await gardenLoginRequest(email, password)).token;
  } catch (e) {
    return { error: messageFor(e), values: { email } };
  }
  await setGardenSessionCookie(token);
  redirect('/garden');
}

export async function gardenLogoutAction(): Promise<void> {
  const store = await cookies();
  const token = store.get(GARDEN_SESSION_COOKIE)?.value;
  if (token) {
    try {
      await gardenLogoutRequest(token);
    } catch {
      // API に届かなくても、この端末の Cookie は消す（サーバー側の印は期限で消える）。利用者の Cookie は触らない
    }
  }
  store.delete(GARDEN_SESSION_COOKIE);
  redirect('/garden/login');
}
