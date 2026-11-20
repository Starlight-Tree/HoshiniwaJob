import type { ReactNode } from 'react';
import { logoutAction } from '../../src/actions/auth';
import { AccountMenu } from '../../src/components/AccountMenu';
import { AppSidebar } from '../../src/components/AppSidebar';
import { currentUser, displayName } from '../../src/lib/session';

const SEARCH_NAV = { href: '/', label: '求人を探す' };

export default async function SiteLayout({ children }: { children: ReactNode }) {
  const user = await currentUser();
  return (
    <div className="app-shell">
      <AppSidebar brand="JobNavi" brandHref="/" navLabel="メインメニュー" items={[{ href: '/', label: '求人を探す', icon: 'search', alsoCurrentUnder: ['/recruits'] }]}>
        {user ? (
          <AccountMenu
            name={displayName(user)}
            email={user.email}
            image={user.avatar_url}
            nav={SEARCH_NAV}
            profile={{ displayName: user.display_name }}
            logout={logoutAction}
          />
        ) : (
          <AccountMenu nav={SEARCH_NAV} loginHref="/login" />
        )}
      </AppSidebar>
      <div className="app-main">
        <div className="app-content">
          {children}
          <p className="site-note">JobNavi は、練習用に作られた架空のサイトです。掲載している法人・求人・給与（通貨「ルミ」）は、すべて架空のものです。</p>
        </div>
      </div>
    </div>
  );
}
