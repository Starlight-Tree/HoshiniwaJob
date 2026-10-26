import type { Metadata } from 'next';
import Link from 'next/link';
import { redirect } from 'next/navigation';
import { loginAction } from '../../../src/actions/auth';
import { LoginForm } from '../../../src/components/AuthForm';
import { currentUser } from '../../../src/lib/session';

export const dynamic = 'force-dynamic';
export const metadata: Metadata = { title: 'ログイン' };

export default async function LoginPage() {
  if (await currentUser()) redirect('/');
  return (
    <main className="auth-main">
      <div className="auth-box">
        <h1>ログイン</h1>
        <LoginForm action={loginAction} />
        <div className="auth-alt">
          <p>はじめての方はこちら</p>
          <Link href="/register" className="outline-button">
            会員登録（無料）
          </Link>
        </div>
      </div>
    </main>
  );
}
