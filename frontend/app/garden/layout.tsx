import type { ReactNode } from 'react';
import { gardenLogoutAction } from '../../src/actions/garden';
import { AccountMenu } from '../../src/components/AccountMenu';
import { AppSidebar } from '../../src/components/AppSidebar';
import { SiteFooter } from '../../src/components/SiteFooter';
import { currentGarden } from '../../src/lib/session';

// 園の管理の画面。求職者の画面（(site)・(auth)）とは別のサイドパネルで、ログインの印（Cookie）も別。ログインしていない間（/garden/login）は、行き先もアカウントも出さない
export default async function GardenLayout({ children }: { children: ReactNode }) {
  const garden = await currentGarden();
  return (
    <div className="app-shell">
      <AppSidebar
        brand="HoshiniwaJob"
        brandHref="/garden"
        brandSub="園の管理"
        navLabel="園のメニュー"
        items={
          garden
            ? [
                { href: '/garden', label: 'ダッシュボード', icon: 'dashboard' },
                { href: '/', label: '公開画面を見る', icon: 'external' },
              ]
            : []
        }
      >
        {garden ? <AccountMenu name={garden.corporate} email={garden.email} honorific="御中" logout={gardenLogoutAction} /> : <AccountMenu />}
      </AppSidebar>
      <div className="app-main">
        <div className="app-content">{children}</div>
        <SiteFooter />
      </div>
    </div>
  );
}
