import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { THEME_KEY } from '../lib/theme';

vi.mock('../actions/auth', () => ({ updateNameAction: vi.fn(async () => ({})) }));
import { AccountMenu } from './AccountMenu';

const setup = () => render(<AccountMenu name="試験 花子" email="hanako@example.com" logout={vi.fn(async () => {})} />);
const openButton = () => screen.getByRole('button', { name: '試験 花子のアカウントメニュー' });

afterEach(() => {
  delete document.documentElement.dataset.theme;
  window.localStorage.removeItem(THEME_KEY);
});

describe('AccountMenu（ログイン中）', () => {
  it('はじめは閉じていて、押すと名前・メール・テーマ・ログアウトが出る', async () => {
    setup();
    const button = openButton();
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('hanako@example.com')).not.toBeInTheDocument();

    await userEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    const menu = screen.getByRole('menu', { name: 'アカウント' });
    // 先頭は、メールアドレスだけ（名前は、パネルを開いているときのボタンに出る。DocuNavi と同じ）
    expect(within(menu).queryByText(/試験 花子/)).not.toBeInTheDocument();
    expect(within(menu).getByText('hanako@example.com')).toBeInTheDocument();
    expect(within(menu).getAllByRole('menuitemradio').map((n) => n.getAttribute('aria-label'))).toEqual(['ライト', 'ダーク', 'システム']);
    expect(within(menu).getByRole('menuitem', { name: 'ログアウト' })).toBeInTheDocument();
  });

  it('開いたら先頭の項目にフォーカスし、↑↓ で動く', async () => {
    setup();
    await userEvent.click(openButton());
    expect(screen.getByRole('menuitemradio', { name: 'ライト' })).toHaveFocus();
    await userEvent.keyboard('{ArrowUp}');
    expect(screen.getByRole('menuitem', { name: 'ログアウト' })).toHaveFocus();
    await userEvent.keyboard('{ArrowDown}');
    expect(screen.getByRole('menuitemradio', { name: 'ライト' })).toHaveFocus();
  });

  it('Esc と、外を押したときに閉じる', async () => {
    setup();
    const button = openButton();
    await userEvent.click(button);
    await userEvent.keyboard('{Escape}');
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(button).toHaveFocus();

    await userEvent.click(button);
    await userEvent.click(document.body);
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });

  describe('プロフィール画像', () => {
    const withImage = (image: string | null | undefined) =>
      render(<AccountMenu name="試験 花子" email="hanako@example.com" image={image} logout={vi.fn(async () => {})} />);
    const img = (container: HTMLElement) => container.querySelector<HTMLImageElement>('.account-avatar img');

    it('https の画像は、アバターに出す（読み上げの対象にはしない）', () => {
      const { container } = withImage('https://lh3.googleusercontent.com/a/example=s96-c');
      expect(img(container)).toHaveAttribute('src', 'https://lh3.googleusercontent.com/a/example=s96-c');
      expect(img(container)).toHaveAttribute('alt', '');
      expect(img(container)).toHaveAttribute('referrerpolicy', 'no-referrer');
      expect(container.querySelector('.account-avatar svg')).toBeNull();
    });

    it('画像が無い・https でない（http・javascript:・data:）ときは、人型アイコン', () => {
      for (const image of [undefined, null, '', 'http://example.com/a.png', 'javascript:alert(1)', 'data:image/png;base64,AAAA']) {
        const { container, unmount } = withImage(image);
        expect(img(container)).toBeNull();
        expect(container.querySelector('.account-avatar svg')).not.toBeNull();
        unmount();
      }
    });

    it('画像を読めなかったら、人型アイコンに戻す', () => {
      const { container } = withImage('https://example.com/broken.png');
      fireEvent.error(img(container)!);
      expect(img(container)).toBeNull();
      expect(container.querySelector('.account-avatar svg')).not.toBeNull();
    });

    it('ログインしていないときは、画像を渡されても出さない', () => {
      const { container } = render(<AccountMenu image="https://example.com/a.png" loginHref="/login" />);
      expect(img(container)).toBeNull();
    });
  });

  it('テーマを選ぶと適用して保存し、「システム」で選択を取り消す。開き直すと、保存した選択が選ばれている', async () => {
    setup();
    await userEvent.click(openButton());
    await userEvent.click(screen.getByRole('menuitemradio', { name: 'ダーク' }));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(window.localStorage.getItem(THEME_KEY)).toBe('dark');
    expect(screen.getByRole('menuitemradio', { name: 'ダーク' })).toHaveAttribute('aria-checked', 'true');

    await userEvent.keyboard('{Escape}');
    await userEvent.click(openButton());
    expect(screen.getByRole('menuitemradio', { name: 'ダーク' })).toHaveAttribute('aria-checked', 'true');

    await userEvent.click(screen.getByRole('menuitemradio', { name: 'システム' }));
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(window.localStorage.getItem(THEME_KEY)).toBeNull();
    expect(screen.getByRole('menuitemradio', { name: 'システム' })).toHaveAttribute('aria-checked', 'true');
  });
});

describe('AccountMenu（パネルを開いたときの名前と矢印）', () => {
  it('ボタンに、名前と矢印を持つ（見せるかどうかは、サイドパネルの開閉を見る CSS が決める。読み上げの名前は変えない）', () => {
    setup();
    const button = openButton();
    expect(within(button).getByText('試験 花子')).toHaveAttribute('aria-hidden', 'true');
    expect(within(button).getByText('▴')).toHaveAttribute('aria-hidden', 'true');
    expect(button).toHaveAccessibleName('試験 花子のアカウントメニュー');
  });
});

describe('AccountMenu（ログインしていない）', () => {
  it('テーマと、Google でログインする入口だけを出す（ログアウトは出さない）', async () => {
    render(<AccountMenu loginHref="/login" />);
    const button = screen.getByRole('button', { name: 'メニュー' });
    await userEvent.click(button);
    const menu = screen.getByRole('menu', { name: 'メニュー' });
    expect(within(menu).getByRole('menuitem', { name: 'Google でログイン' })).toHaveAttribute('href', '/login');
    expect(within(menu).getAllByRole('menuitemradio')).toHaveLength(3);
    expect(within(menu).queryByRole('menuitem', { name: 'ログアウト' })).not.toBeInTheDocument();
  });

  it('行き先が無ければ（園のログイン画面）、テーマだけを出す', async () => {
    render(<AccountMenu />);
    await userEvent.click(screen.getByRole('button', { name: 'メニュー' }));
    const menu = screen.getByRole('menu', { name: 'メニュー' });
    expect(within(menu).getAllByRole('menuitemradio')).toHaveLength(3);
    expect(within(menu).queryByRole('menuitem')).not.toBeInTheDocument();
  });
});

describe('AccountMenu（DocuNavi と同じ項目）', () => {
  const nav = { href: '/', label: '求人を探す' };
  const profile = { displayName: '花子' };
  const logout = vi.fn(async () => {});

  it('ログイン中の項目と順は、メール → 画面への入口 → テーマ → 表示名を変更 → ログアウト', async () => {
    render(<AccountMenu name="試験 花子" email="hanako@example.com" nav={nav} profile={profile} logout={logout} />);
    await userEvent.click(screen.getByRole('button', { name: '試験 花子のアカウントメニュー' }));
    const menu = screen.getByRole('menu', { name: 'アカウント' });
    const order = [...menu.querySelectorAll('.account-who, [role^="menuitem"]')].map((e) => (e.getAttribute('aria-label') ?? e.textContent ?? '').trim());
    expect(order).toEqual(['hanako@example.com', '求人を探す', 'ライト', 'ダーク', 'システム', '表示名を変更', 'ログアウト']);
    expect(within(menu).getByRole('menuitem', { name: '求人を探す' })).toHaveAttribute('href', '/');
  });

  it('ログインしていない人にも、画面への入口を出す（ナレッジを出す DocuNavi と同じ）', async () => {
    render(<AccountMenu nav={nav} loginHref="/login" />);
    await userEvent.click(screen.getByRole('button', { name: 'メニュー' }));
    const menu = screen.getByRole('menu', { name: 'メニュー' });
    expect(within(menu).getByRole('menuitem', { name: '求人を探す' })).toBeInTheDocument();
    expect(within(menu).queryByRole('menuitem', { name: '表示名を変更' })).not.toBeInTheDocument();
  });

  it('profile を渡さなければ（園）、表示名を変更は出さない', async () => {
    render(<AccountMenu name="環軌道植物公社" email="garden@example.com" nav={{ href: '/garden', label: 'ダッシュボード' }} logout={logout} />);
    await userEvent.click(screen.getByRole('button', { name: '環軌道植物公社のアカウントメニュー' }));
    expect(screen.queryByRole('menuitem', { name: '表示名を変更' })).not.toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'ダッシュボード' })).toHaveAttribute('href', '/garden');
  });

  it('表示名を変更を押すと、メニューを閉じて、いまの表示名が入ったダイアログを開く', async () => {
    render(<AccountMenu name="試験 花子" email="hanako@example.com" nav={nav} profile={profile} logout={logout} />);
    const button = screen.getByRole('button', { name: '試験 花子のアカウントメニュー' });
    await userEvent.click(button);
    await userEvent.click(screen.getByRole('menuitem', { name: '表示名を変更' }));
    expect(button).toHaveAttribute('aria-expanded', 'false');
    const dialog = screen.getByRole('dialog', { name: '表示名を変更' });
    expect(within(dialog).getByLabelText('表示名')).toHaveValue('花子');
  });
});
