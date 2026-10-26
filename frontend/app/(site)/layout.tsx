import Link from 'next/link';
import type { ReactNode } from 'react';
import { logoutAction } from '../../src/actions/auth';
import { AccountMenu } from '../../src/components/AccountMenu';
import { currentUser, displayName } from '../../src/lib/session';

export default async function SiteLayout({ children }: { children: ReactNode }) {
  const user = await currentUser();
  return (
    <>
      <header className="site-header">
        <div className="inner">
          <Link href="/" className="logo">
            星庭ジョブ
          </Link>
          <nav aria-label="メインメニュー">
            <Link href="/">求人を探す</Link>
            {user ? (
              <AccountMenu name={displayName(user)} email={user.email} logout={logoutAction} />
            ) : (
              <Link href="/login" className="header-cta">
                ログイン・会員登録
              </Link>
            )}
          </nav>
        </div>
      </header>
      {children}
    </>
  );
}
