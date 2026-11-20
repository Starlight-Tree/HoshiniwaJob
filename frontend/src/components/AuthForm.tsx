'use client';

import { useActionState } from 'react';
import { initialFormState, type FormAction } from '../lib/form-state';
import { Field } from './Field';

type Props = { action: FormAction };

function Alert({ message }: { message?: string }) {
  return message ? (
    <p className="form-alert" role="alert">
      {message}
    </p>
  ) : null;
}

export function LoginForm({ action }: Props) {
  const [state, formAction, pending] = useActionState(action, initialFormState);
  return (
    <form className="auth-form" action={formAction} noValidate>
      <Alert message={state.error} />
      <Field name="email" label="メールアドレス" type="email" autoComplete="email" defaultValue={state.values?.email} error={state.fieldErrors?.email} />
      <Field name="password" label="パスワード" type="password" autoComplete="current-password" error={state.fieldErrors?.password} />
      <button type="submit" className="primary-button" disabled={pending}>
        {pending ? '送信中…' : 'ログイン'}
      </button>
    </form>
  );
}
