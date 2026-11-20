import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { googleLoginAction } from '../../../src/actions/auth';
import { loginErrorMessage } from '../../../src/lib/login-error';
import { currentUser } from '../../../src/lib/session';

export const dynamic = 'force-dynamic';
export const metadata: Metadata = { title: 'ログイン' };

// DocuNavi と同じく、ログインは Google アカウントだけ（はじめての方は、ログインすると、そのまま登録される）。画面は、見出し・1 行の案内・ボタンだけにする。
export default async function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  if (await currentUser()) redirect('/');
  const message = loginErrorMessage((await searchParams).error);
  return (
    <main className="auth-main">
      <div className="auth-box">
        <h1>ログイン</h1>
        <p className="auth-lead">Google アカウントでログインしてください</p>
        {message ? (
          <p className="form-alert login-alert" role="alert">
            {message}
          </p>
        ) : null}
        {/* サーバーアクションのフォーム。JavaScript の読み込み前でも押せる */}
        <form action={googleLoginAction}>
          <button type="submit" className="primary-button google-login">
            Google でログイン
          </button>
        </form>
      </div>
    </main>
  );
}
