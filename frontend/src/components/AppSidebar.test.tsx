import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AppSidebar } from './AppSidebar';

const nav = vi.hoisted(() => ({ pathname: '/' }));
vi.mock('next/navigation', () => ({ usePathname: () => nav.pathname }));

const items = [{ href: '/', label: '求人を探す', alsoCurrentUnder: ['/recruits'] }];
const setup = (pathname: string, props: Partial<Parameters<typeof AppSidebar>[0]> = {}) => {
  nav.pathname = pathname;
  return render(
    <AppSidebar brand="星庭ジョブ" brandHref="/" navLabel="メインメニュー" items={items} {...props}>
      <p>下部の中身</p>
    </AppSidebar>,
  );
};

describe('AppSidebar', () => {
  it('ロゴ・行き先・テーマの切り替え・下部の中身を出す', () => {
    setup('/');
    expect(screen.getByRole('link', { name: '星庭ジョブ' })).toHaveAttribute('href', '/');
    const menu = screen.getByRole('navigation', { name: 'メインメニュー' });
    expect(within(menu).getByRole('link', { name: '求人を探す' })).toHaveAttribute('href', '/');
    expect(screen.getByRole('group', { name: 'テーマ' })).toBeInTheDocument();
    expect(screen.getByText('下部の中身')).toBeInTheDocument();
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
      items: [{ href: '/garden', label: 'ダッシュボード' }, { href: '/', label: '公開画面を見る' }],
    });
    expect(screen.getByRole('link', { name: 'ダッシュボード' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: '公開画面を見る' })).not.toHaveAttribute('aria-current');
  });

  it('/gardenia のような、頭だけ同じ別のパスは、/garden の続きとみなさない', () => {
    setup('/gardenia', { items: [{ href: '/garden', label: 'ダッシュボード' }] });
    expect(screen.getByRole('link', { name: 'ダッシュボード' })).not.toHaveAttribute('aria-current');
  });

  it('行き先が無ければ、ナビゲーションを出さない（ログイン前の園）', () => {
    setup('/garden/login', { items: [] });
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'テーマ' })).toBeInTheDocument();
  });

  it('副見出しを出せる', () => {
    setup('/garden', { brandSub: '園の管理' });
    expect(screen.getByText('園の管理')).toBeInTheDocument();
  });

  it('狭い画面のメニューボタンで、開閉の状態が切り替わる', async () => {
    setup('/');
    const toggle = screen.getByRole('button', { name: 'メニュー' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    const bodyId = toggle.getAttribute('aria-controls');
    expect(bodyId).toBeTruthy();
    expect(document.getElementById(bodyId ?? '')).toHaveClass('app-sidebar-body');
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('complementary')).toHaveAttribute('data-open', 'true');
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('画面を移ったら、開いていたメニューを閉じる', async () => {
    const { rerender } = setup('/');
    await userEvent.click(screen.getByRole('button', { name: 'メニュー' }));
    expect(screen.getByRole('button', { name: 'メニュー' })).toHaveAttribute('aria-expanded', 'true');
    nav.pathname = '/recruits/abc';
    rerender(
      <AppSidebar brand="星庭ジョブ" brandHref="/" navLabel="メインメニュー" items={items}>
        <p>下部の中身</p>
      </AppSidebar>,
    );
    expect(screen.getByRole('button', { name: 'メニュー' })).toHaveAttribute('aria-expanded', 'false');
  });

  it('今と同じパスへのリンクを押しても（条件だけが変わる移動）、メニューを閉じる', async () => {
    setup('/');
    const toggle = screen.getByRole('button', { name: 'メニュー' });
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await userEvent.click(screen.getByRole('link', { name: '求人を探す' }));
    expect(toggle).toHaveAttribute('aria-expanded', 'false');

    await userEvent.click(toggle);
    await userEvent.click(screen.getByRole('link', { name: '星庭ジョブ' }));
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });
});
