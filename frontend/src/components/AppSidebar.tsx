'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { BrandIcon, NavIcon, SidebarIcon } from './icons';
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
 * 左のサイドパネル（DocuNavi と同じ。開いた表示と、アイコンだけの細い帯を、ボタンで切り替える）。
 * 開いた表示: 上にロゴと名前・閉じるボタン、続いて行き先（アイコン＋名前）、下にアカウント（アバター＋名前）。はじめは開いた状態で、保存はしない。
 * 閉じた表示（細い帯）: ロゴの位置が「サイドパネルを開く」ボタンになる（ホバー・フォーカスで、ロゴが開閉の絵に変わる）。名前は、ホバーとキーボードのフォーカスで、アイコンの右に出る。
 * 開閉できるのは 1176px 以上（開くと、求人検索の「しぼり込み」と結果が並ぶ幅が足りなくなるため）。それより狭い間は、開閉のボタンを出さず、細い帯のまま。
 * 976px 未満は、上の横の帯になり、名前を文字で見せる。開いている画面の項目には `aria-current="page"` を付ける。
 * 項目の名前は、閉じた表示では画面に出さない文字（`.app-rail-label`）で持つ（読み上げの名前になり、開いた表示と狭い画面では見える）。
 * 開閉の見た目（アカウントの名前を出すことを含む）は、`data-open` を見る CSS が決める。アカウントのメニューはサーバーの layout から渡されるので、開閉の状態は props では渡さない。
 */
export function AppSidebar({ brand, brandHref, brandSub, navLabel, items, children }: Props) {
  const pathname = usePathname();
  const brandName = brandSub ? `${brand} ${brandSub}` : brand;
  const [open, setOpen] = useState(true);
  const openRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const toggled = useRef(false);
  // 開閉したら、フォーカスを、いま押せる側のボタンへ移す（消えたボタンにフォーカスを残さない）
  useEffect(() => {
    if (!toggled.current) return;
    (open ? closeRef.current : openRef.current)?.focus();
  }, [open]);
  const toggle = (next: boolean) => {
    toggled.current = true;
    setOpen(next);
  };
  return (
    <aside className="app-sidebar" data-open={open ? 'true' : 'false'}>
      <nav className="app-rail" aria-label={navLabel}>
        <div className="app-brand-row">
          <Link href={brandHref} className="app-rail-btn app-rail-logo app-brand-link" data-tip={brandName}>
            <BrandIcon />
            <span className="app-rail-label app-brand-name">
              {brand}
              {brandSub ? (
                <>
                  {' '}
                  <span className="app-brand-sub">{brandSub}</span>
                </>
              ) : null}
            </span>
          </Link>
          {open ? (
            <button ref={closeRef} type="button" className="app-icon-btn app-toggle" aria-label="サイドパネルを閉じる" aria-expanded="true" onClick={() => toggle(false)}>
              <SidebarIcon />
            </button>
          ) : (
            <button ref={openRef} type="button" className="app-rail-btn app-rail-logo app-open-btn app-toggle" aria-label="サイドパネルを開く" aria-expanded="false" data-tip="サイドパネルを開く" onClick={() => toggle(true)}>
              <BrandIcon />
              <span className="app-open-icon">
                <SidebarIcon />
              </span>
            </button>
          )}
        </div>
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
