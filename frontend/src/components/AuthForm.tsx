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

export function RegisterForm({ action }: Props) {
  const [state, formAction, pending] = useActionState(action, initialFormState);
  return (
    <form className="auth-form" action={formAction} noValidate>
      <Alert message={state.error} />
      <div className="field-pair">
        <Field name="last_name" label="姓" autoComplete="family-name" defaultValue={state.values?.last_name} error={state.fieldErrors?.last_name} />
        <Field name="first_name" label="名" autoComplete="given-name" defaultValue={state.values?.first_name} error={state.fieldErrors?.first_name} />
      </div>
      <Field name="email" label="メールアドレス" type="email" autoComplete="email" defaultValue={state.values?.email} error={state.fieldErrors?.email} />
      <Field name="password" label="パスワード（8〜128 文字）" type="password" autoComplete="new-password" error={state.fieldErrors?.password} />
      <button type="submit" className="primary-button" disabled={pending}>
        {pending ? '送信中…' : '登録してログインする'}
      </button>
    </form>
  );
}
