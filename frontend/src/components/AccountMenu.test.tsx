import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { THEME_KEY } from '../lib/theme';
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
  it('テーマと、ログイン・会員登録の入口だけを出す（ログアウトは出さない）', async () => {
    render(<AccountMenu loginHref="/login" />);
    const button = screen.getByRole('button', { name: 'メニュー' });
    await userEvent.click(button);
    const menu = screen.getByRole('menu', { name: 'メニュー' });
    expect(within(menu).getByRole('menuitem', { name: 'ログイン・会員登録' })).toHaveAttribute('href', '/login');
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
