import Link from 'next/link';
import type { ReactNode } from 'react';
import { SiteFooter } from '../../src/components/SiteFooter';
import { ThemeSwitch } from '../../src/components/ThemeSwitch';

// ログイン・会員登録の画面は、迷わないよう、サイドパネルを出さず、ヘッダーを「← 求人を探す」とテーマの切り替えだけにする
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
            <ThemeSwitch />
          </nav>
        </div>
      </header>
      {children}
      <SiteFooter />
    </>
  );
}
