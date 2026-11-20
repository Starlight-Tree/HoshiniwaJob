import Link from 'next/link';
import type { ReactNode } from 'react';
import { logoutAction } from '../../src/actions/auth';
import { AccountMenu } from '../../src/components/AccountMenu';
import { AppSidebar } from '../../src/components/AppSidebar';
import { SiteFooter } from '../../src/components/SiteFooter';
import { currentUser, displayName } from '../../src/lib/session';

export default async function SiteLayout({ children }: { children: ReactNode }) {
  const user = await currentUser();
  return (
    <div className="app-shell">
      <AppSidebar brand="星庭ジョブ" brandHref="/" navLabel="メインメニュー" items={[{ href: '/', label: '求人を探す', alsoCurrentUnder: ['/recruits'] }]}>
        {user ? (
          <AccountMenu name={displayName(user)} email={user.email} logout={logoutAction} />
        ) : (
          <Link href="/login" className="header-cta">
            ログイン・会員登録
          </Link>
        )}
      </AppSidebar>
      <div className="app-main">
        <div className="app-content">{children}</div>
        <SiteFooter />
      </div>
    </div>
  );
}
