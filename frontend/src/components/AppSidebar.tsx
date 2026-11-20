'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useId, useState } from 'react';
import type { ReactNode } from 'react';
import { ThemeSwitch } from './ThemeSwitch';

export type SidebarItem = {
  href: string;
  label: string;
  /** この項目を「いま開いている画面」とみなす、追加のパスの頭（例: 求人詳細は求人検索の続き）。`href` 自身とその配下は、指定なしでも当たる（`href` が '/' のときは、'/' そのものだけ）。 */
  alsoCurrentUnder?: readonly string[];
};

type Props = {
  /** ロゴの文字と、その行き先。 */
  brand: string;
  brandHref: string;
  /** ロゴの下の小さな見出し（例: 園の管理）。 */
  brandSub?: string;
  /** ナビゲーションの名前（読み上げ用）。 */
  navLabel: string;
  items: readonly SidebarItem[];
  /** 下部（テーマ切り替えの下）に出すもの。アカウントのメニューやログインの入口。 */
  children?: ReactNode;
};

function isCurrent(pathname: string, item: SidebarItem): boolean {
  const under = (base: string) => (base === '/' ? false : pathname === base || pathname.startsWith(`${base}/`));
  if (item.href === '/' ? pathname === '/' : under(item.href)) return true;
  return (item.alsoCurrentUnder ?? []).some(under);
}

/**
 * 左のサイドパネル。ロゴ・主な行き先・（下部に）テーマ切り替えとアカウント。狭い画面（スマホ幅）では、上の帯になり、「メニュー」ボタンで開閉する。
 * 開いている画面の項目には `aria-current="page"` を付ける。画面を移ったら（パスが変わったとき）と、リンクを押したときは、狭い画面のメニューを閉じる（同じパスで、条件だけ変わる移動でも閉じる）。
 */
export function AppSidebar({ brand, brandHref, brandSub, navLabel, items, children }: Props) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const bodyId = useId();

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <aside className="app-sidebar" data-open={open}>
      <div className="app-sidebar-head">
        <Link href={brandHref} className="app-brand" onClick={() => setOpen(false)}>
          {brand}
          {brandSub ? <span className="app-brand-sub">{brandSub}</span> : null}
        </Link>
        <button type="button" className="app-sidebar-toggle" aria-expanded={open} aria-controls={bodyId} onClick={() => setOpen((v) => !v)}>
          メニュー
        </button>
      </div>
      <div id={bodyId} className="app-sidebar-body">
        {items.length > 0 ? (
          <nav aria-label={navLabel}>
            <ul className="app-nav">
              {items.map((item) => (
                <li key={item.href}>
                  <Link href={item.href} aria-current={isCurrent(pathname, item) ? 'page' : undefined} onClick={() => setOpen(false)}>
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ) : null}
        <div className="app-sidebar-foot">
          <ThemeSwitch />
          {children}
        </div>
      </div>
    </aside>
  );
}
