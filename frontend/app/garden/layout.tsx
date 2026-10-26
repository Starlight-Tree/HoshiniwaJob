import Link from 'next/link';
import type { ReactNode } from 'react';
import { gardenLogoutAction } from '../../src/actions/garden';
import { AccountMenu } from '../../src/components/AccountMenu';
import { currentGarden } from '../../src/lib/session';

// 園の管理の画面。求職者の画面（(site)・(auth)）とは別のヘッダーで、ログインの印（Cookie）も別
export default async function GardenLayout({ children }: { children: ReactNode }) {
  const garden = await currentGarden();
  return (
    <>
      <header className="site-header">
        <div className="inner">
          <Link href="/garden" className="logo">
            星庭ジョブ <span className="logo-sub">園の管理</span>
          </Link>
          <nav aria-label="園のメニュー">
            {garden ? (
              <AccountMenu name={garden.corporate} email={garden.email} honorific="御中" logout={gardenLogoutAction} />
            ) : null}
          </nav>
        </div>
      </header>
      {children}
    </>
  );
}
