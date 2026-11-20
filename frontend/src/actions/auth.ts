'use server';

import { revalidatePath } from 'next/cache';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { ApiError, loginRequest, logoutRequest, registerRequest, updateNameRequest } from '../lib/api';
import { messageFor } from '../lib/error-message';
import type { FormState } from '../lib/form-state';
import { SESSION_COOKIE, setRegisteredFlag, setSessionCookie } from '../lib/session';
import { validateLogin, validateName, validateRegister } from '../lib/validation';

const text = (data: FormData, key: string) => String(data.get(key) ?? '');

export async function loginAction(_prev: FormState, data: FormData): Promise<FormState> {
  const email = text(data, 'email').trim();
  const password = text(data, 'password');
  const fieldErrors = validateLogin({ email, password });
  if (Object.keys(fieldErrors).length > 0) return { fieldErrors, values: { email } };

  let token: string;
  try {
    token = (await loginRequest(email, password)).token;
  } catch (e) {
    return { error: messageFor(e), values: { email } };
  }
  await setSessionCookie(token);
  redirect('/');
}

export async function registerAction(_prev: FormState, data: FormData): Promise<FormState> {
  const input = {
    last_name: text(data, 'last_name').trim(),
    first_name: text(data, 'first_name').trim(),
    email: text(data, 'email').trim(),
    password: text(data, 'password'),
  };
  const values = { last_name: input.last_name, first_name: input.first_name, email: input.email };
  const fieldErrors = validateRegister(input);
  if (Object.keys(fieldErrors).length > 0) return { fieldErrors, values };

  let token: string;
  try {
    token = (await registerRequest(input)).token;
  } catch (e) {
    return { error: messageFor(e), values };
  }
  await setSessionCookie(token);
  await setRegisteredFlag();
  redirect('/');
}

/** お名前（姓・名）の変更。ログイン中の本人のものだけ変えられる（API が、トークンの持ち主で決める）。 */
export async function updateNameAction(_prev: FormState, data: FormData): Promise<FormState> {
  const values = { last_name: text(data, 'last_name').trim(), first_name: text(data, 'first_name').trim() };
  const fieldErrors = validateName(values);
  if (Object.keys(fieldErrors).length > 0) return { fieldErrors, values };
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return { error: 'ログインしてください', values };
  try {
    await updateNameRequest(token, values);
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return { error: 'ログインの有効期限が切れました。もう一度ログインしてください', values };
    return { error: e instanceof ApiError && e.status === 422 ? '入力内容を確認してください' : messageFor(e), values };
  }
  revalidatePath('/', 'layout'); // サイドパネルの名前を、新しい名前にする
  return { saved: true, values };
}

export async function logoutAction(): Promise<void> {
  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;
  if (token) {
    try {
      await logoutRequest(token);
    } catch {
      // API に届かなくても、この端末の Cookie は消す（サーバー側の印は期限で消える）
    }
  }
  store.delete(SESSION_COOKIE);
  redirect('/');
}
