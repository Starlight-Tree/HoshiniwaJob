'use client';

import { useId, useState } from 'react';

type Props = {
  name: string;
  label: string;
  type?: 'text' | 'email' | 'password';
  autoComplete: string;
  defaultValue?: string;
  error?: string;
};

/** ラベル・入力欄・エラー文の 1 組。パスワードだけ、表示・非表示の切り替えが付く。 */
export function Field({ name, label, type = 'text', autoComplete, defaultValue, error }: Props) {
  const id = useId();
  const [shown, setShown] = useState(false);
  const isPassword = type === 'password';
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className={isPassword ? 'password-row' : undefined}>
        <input
          id={id}
          name={name}
          type={isPassword && shown ? 'text' : type}
          autoComplete={autoComplete}
          defaultValue={defaultValue}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          spellCheck={false}
        />
        {isPassword ? (
          <button type="button" className="toggle-password" aria-pressed={shown} onClick={() => setShown((v) => !v)}>
            {shown ? '隠す' : '表示'}
          </button>
        ) : null}
      </div>
      {error ? (
        <p id={`${id}-error`} className="field-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
