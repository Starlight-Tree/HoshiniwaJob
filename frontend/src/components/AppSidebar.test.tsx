import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AppSidebar } from './AppSidebar';

const nav = vi.hoisted(() => ({ pathname: '/' }));
vi.mock('next/navigation', () => ({ usePathname: () => nav.pathname }));

const items = [{ href: '/', label: '求人を探す', icon: 'search' as const, alsoCurrentUnder: ['/recruits'] }];
const setup = (pathname: string, props: Partial<Parameters<typeof AppSidebar>[0]> = {}) => {
  nav.pathname = pathname;
  return render(
    <AppSidebar brand="HoshiniwaJob" brandHref="/" navLabel="メインメニュー" items={items} {...props}>
      <p>下部の中身</p>
    </AppSidebar>,
  );
};

describe('AppSidebar', () => {
  it('ロゴ・行き先・下部の中身を出す（名前は、画面に出さない文字で持つ）', () => {
    setup('/');
    const menu = screen.getByRole('navigation', { name: 'メインメニュー' });
    expect(within(menu).getByRole('link', { name: 'HoshiniwaJob' })).toHaveAttribute('href', '/');
    expect(within(menu).getByRole('link', { name: '求人を探す' })).toHaveAttribute('href', '/');
    expect(screen.getByText('下部の中身')).toBeInTheDocument();
    // 名前は、ホバーで出るツールチップの文字にもなる
    expect(screen.getByRole('link', { name: '求人を探す' })).toHaveAttribute('data-tip', '求人を探す');
  });

  it('テーマの切り替えは、サイドパネルには出さない（アカウントのメニューの中）', () => {
    setup('/');
    expect(screen.queryByRole('group', { name: 'テーマ' })).not.toBeInTheDocument();
  });

  it('開いている画面の項目に aria-current を付ける（求人詳細は、求人検索の続き）', () => {
    const { unmount } = setup('/');
    expect(screen.getByRole('link', { name: '求人を探す' })).toHaveAttribute('aria-current', 'page');
    unmount();
    setup('/recruits/abc');
    expect(screen.getByRole('link', { name: '求人を探す' })).toHaveAttribute('aria-current', 'page');
  });

  it('「/」の項目は、無関係なパスでは current にならず、配下の判定は境界で区切る', () => {
    const { unmount } = setup('/login');
    expect(screen.getByRole('link', { name: '求人を探す' })).not.toHaveAttribute('aria-current');
    unmount();
    setup('/garden/recruits/1/images', {
      items: [
        { href: '/garden', label: 'ダッシュボード', icon: 'dashboard' },
        { href: '/', label: '公開画面を見る', icon: 'external' },
      ],
    });
    expect(screen.getByRole('link', { name: 'ダッシュボード' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: '公開画面を見る' })).not.toHaveAttribute('aria-current');
  });

  it('/gardenia のような、頭だけ同じ別のパスは、/garden の続きとみなさない', () => {
    setup('/gardenia', { items: [{ href: '/garden', label: 'ダッシュボード', icon: 'dashboard' }] });
    expect(screen.getByRole('link', { name: 'ダッシュボード' })).not.toHaveAttribute('aria-current');
  });

  it('行き先が無ければ、ロゴのリンクだけを出す（ログイン前の園）', () => {
    setup('/garden/login', { items: [] });
    const menu = screen.getByRole('navigation', { name: 'メインメニュー' });
    expect(within(menu).getAllByRole('link')).toHaveLength(1);
  });

  it('副見出しは、ロゴの名前に足す', () => {
    setup('/garden', { brandSub: '園の管理' });
    expect(screen.getByRole('link', { name: 'HoshiniwaJob 園の管理' })).toHaveAttribute('href', '/');
  });
});
