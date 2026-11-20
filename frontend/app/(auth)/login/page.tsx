import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { googleErrorMessage } from '../../../src/lib/google';
import { currentUser } from '../../../src/lib/session';

export const dynamic = 'force-dynamic';
export const metadata: Metadata = { title: 'ログイン' };

// DocuNavi と同じく、ログインは Google アカウントだけ。はじめての方は、ログインすると、そのまま登録される。
export default async function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  if (await currentUser()) redirect('/');
  const message = googleErrorMessage((await searchParams).error);
  return (
    <main className="auth-main">
      <div className="auth-box">
        <h1>ログイン</h1>
        <p className="auth-lead">Google アカウントでログインしてください。はじめての方は、ログインすると、そのまま登録されます。</p>
        {message ? (
          <p className="form-alert" role="alert">
            {message}
          </p>
        ) : null}
        {/* 先読み（prefetch）で入口の処理が走らないよう、next/link ではなく普通のリンクにする */}
        <a href="/auth/google/start" className="primary-button inline google-login">
          Google でログイン
        </a>
      </div>
    </main>
  );
}
