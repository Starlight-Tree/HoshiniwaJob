import type { Metadata } from 'next';
import Link from 'next/link';
import { redirect } from 'next/navigation';
import { registerAction } from '../../../src/actions/auth';
import { RegisterForm } from '../../../src/components/AuthForm';
import { currentUser } from '../../../src/lib/session';

export const dynamic = 'force-dynamic';
export const metadata: Metadata = { title: '会員登録' };

export default async function RegisterPage() {
  if (await currentUser()) redirect('/');
  return (
    <main className="auth-register">
      <section className="auth-intro">
        <h1>会員登録（無料）</h1>
        <p>お名前・メールアドレス・パスワードの 3 つだけで登録できます。登録すると、そのままログインした状態になります。</p>
        <ol>
          <li>
            <span>1</span>必要事項を入力する
          </li>
          <li>
            <span>2</span>登録と同時にログイン
          </li>
        </ol>
        <p className="auth-intro-alt">
          すでに登録済みの方は <Link href="/login">ログイン</Link>
        </p>
      </section>
      <RegisterForm action={registerAction} />
    </main>
  );
}
