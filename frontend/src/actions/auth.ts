'use server';

import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { ApiError, loginRequest, logoutRequest, registerRequest } from '../lib/api';
import type { FormState } from '../lib/form-state';
import { SESSION_COOKIE, setRegisteredFlag, setSessionCookie } from '../lib/session';
import { validateLogin, validateRegister } from '../lib/validation';

const text = (data: FormData, key: string) => String(data.get(key) ?? '');

// API の応答は、ここで固定の文に直す（API の本文や例外の文字列は画面に出さない）
function messageFor(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 401) return 'メールアドレスまたはパスワードが違います';
    if (e.status === 409) return 'このメールアドレスは登録できません';
    if (e.status === 422) return '入力内容を確認してください';
  }
  return 'ただいま利用できません。しばらくしてから、もう一度お試しください';
}

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
