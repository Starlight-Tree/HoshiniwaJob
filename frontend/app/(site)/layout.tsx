import type { ReactNode } from 'react';
import { logoutAction } from '../../src/actions/auth';
import { AccountMenu } from '../../src/components/AccountMenu';
import { AppSidebar } from '../../src/components/AppSidebar';
import { SiteFooter } from '../../src/components/SiteFooter';
import { currentUser, displayName } from '../../src/lib/session';

const SEARCH_NAV = { href: '/', label: '求人を探す' };

export default async function SiteLayout({ children }: { children: ReactNode }) {
  const user = await currentUser();
  return (
    <div className="app-shell">
      <AppSidebar brand="HoshiniwaJob" brandHref="/" navLabel="メインメニュー" items={[{ href: '/', label: '求人を探す', icon: 'search', alsoCurrentUnder: ['/recruits'] }]}>
        {user ? (
          <AccountMenu
            name={displayName(user)}
            email={user.email}
            image={user.avatar_url}
            nav={SEARCH_NAV}
            profile={{ lastName: user.last_name, firstName: user.first_name }}
            logout={logoutAction}
          />
        ) : (
          <AccountMenu nav={SEARCH_NAV} loginHref="/login" />
        )}
      </AppSidebar>
      <div className="app-main">
        <div className="app-content">{children}</div>
        <SiteFooter />
      </div>
    </div>
  );
}
