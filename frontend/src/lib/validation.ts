// 入力の検査。最終の判断は API（backend/app/schemas.py）がする。ここは、送る前に分かる誤りを、画面で先に知らせるためのもの。

export type Field = 'last_name' | 'first_name' | 'email' | 'password';
export type FieldErrors = Partial<Record<Field, string>>;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// API は文字数を「文字」で数える。String.length は UTF-16 の単位なので、コードポイントで数える
const count = (s: string) => [...s].length;

function email(value: string): string | undefined {
  if (value === '') return 'メールアドレスを入力してください';
  if (!EMAIL.test(value)) return 'メールアドレスの形式が正しくありません（例: name@example.com）';
  return undefined;
}

function name(value: string, label: string): string | undefined {
  if (value === '') return `${label}を入力してください`;
  if (count(value) > 50) return `${label}は 50 文字以内で入力してください`;
  return undefined;
}

function compact(errors: FieldErrors): FieldErrors {
  return Object.fromEntries(Object.entries(errors).filter(([, v]) => v !== undefined)) as FieldErrors;
}

/** お名前の変更（姓・名）。それぞれ 1〜50 文字。 */
export function validateName(input: { last_name: string; first_name: string }): FieldErrors {
  return compact({ last_name: name(input.last_name, '姓'), first_name: name(input.first_name, '名') });
}

export function validateLogin(input: { email: string; password: string }): FieldErrors {
  return compact({
    email: email(input.email),
    // ログインでは、パスワードの長さの決まりは見せない（空と上限だけ）
    password:
      input.password === ''
        ? 'パスワードを入力してください'
        : count(input.password) > 128
          ? 'パスワードは 128 文字以内で入力してください'
          : undefined,
  });
}
