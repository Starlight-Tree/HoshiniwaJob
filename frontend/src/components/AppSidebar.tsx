'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';
import { BrandIcon, NavIcon } from './icons';
import type { NavIconName } from './icons';

export type SidebarItem = {
  href: string;
  label: string;
  icon: NavIconName;
  /** この項目を「いま開いている画面」とみなす、追加のパスの頭（例: 求人詳細は求人検索の続き）。`href` 自身とその配下は、指定なしでも当たる（`href` が '/' のときは、'/' そのものだけ）。 */
  alsoCurrentUnder?: readonly string[];
};

type Props = {
  /** ロゴの名前（読み上げと、ホバーで出る名前）と、その行き先。 */
  brand: string;
  brandHref: string;
  /** ロゴの名前の後ろに足す、小さな見出し（例: 園の管理）。 */
  brandSub?: string;
  /** ナビゲーションの名前（読み上げ用）。 */
  navLabel: string;
  items: readonly SidebarItem[];
  /** 下部に出すもの（アカウントのメニュー）。 */
  children?: ReactNode;
};

function isCurrent(pathname: string, item: SidebarItem): boolean {
  const under = (base: string) => (base === '/' ? false : pathname === base || pathname.startsWith(`${base}/`));
  if (item.href === '/' ? pathname === '/' : under(item.href)) return true;
  return (item.alsoCurrentUnder ?? []).some(under);
}

/**
 * 左の細い帯（DocuNavi の閉じたサイドバーと同じ形）。上にロゴの絵、続いて行き先のアイコン、下にアカウントのメニュー。名前は、ホバーとキーボードのフォーカスで、アイコンの右に出る。
 * 狭い画面（976px 未満）では、上の横の帯になり、名前を文字で見せる。開いている画面の項目には `aria-current="page"` を付ける。
 * 項目の名前は、画面には出さない文字（`.app-rail-label`）で持つ（読み上げの名前になり、狭い画面では見える）。
 */
export function AppSidebar({ brand, brandHref, brandSub, navLabel, items, children }: Props) {
  const pathname = usePathname();
  const brandName = brandSub ? `${brand} ${brandSub}` : brand;
  return (
    <aside className="app-sidebar">
      <nav className="app-rail" aria-label={navLabel}>
        <Link href={brandHref} className="app-rail-btn app-rail-logo" data-tip={brandName}>
          <BrandIcon />
          <span className="app-rail-label">{brandName}</span>
        </Link>
        {items.map((item) => (
          <Link key={item.href} href={item.href} className="app-rail-btn" data-tip={item.label} aria-current={isCurrent(pathname, item) ? 'page' : undefined}>
            <NavIcon name={item.icon} />
            <span className="app-rail-label">{item.label}</span>
          </Link>
        ))}
      </nav>
      <div className="app-rail-foot">{children}</div>
    </aside>
  );
}
