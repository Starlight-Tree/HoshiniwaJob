import { redirect } from 'next/navigation';

export const dynamic = 'force-dynamic';

// 会員登録の画面は、Google ログインに替えたので無い（はじめての方は、ログインすると、そのまま登録される）。古いリンクは、ログイン画面へ。
export default function RegisterPage(): never {
  redirect('/login');
}
