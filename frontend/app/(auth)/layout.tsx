import Link from 'next/link';
import type { ReactNode } from 'react';

// ログイン・会員登録の画面は、迷わないよう、ヘッダーを「← 求人を探す」だけにする
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <header className="site-header">
        <div className="inner">
          <Link href="/" className="logo">
            星庭ジョブ
          </Link>
          <nav aria-label="メインメニュー">
            <Link href="/">← 求人を探す</Link>
          </nav>
        </div>
      </header>
      {children}
    </>
  );
}
