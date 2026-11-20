import { render, screen, within } from '@testing-library/react';
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
    expect(within(menu).getByText('試験 花子 さん')).toBeInTheDocument();
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

  it('敬称を変えられる（園は「御中」）', async () => {
    render(<AccountMenu name="環軌道植物公社" email="garden@example.com" honorific="御中" logout={vi.fn(async () => {})} />);
    await userEvent.click(screen.getByRole('button', { name: '環軌道植物公社のアカウントメニュー' }));
    expect(screen.getByText('環軌道植物公社 御中')).toBeInTheDocument();
    expect(screen.queryByText(/さん/)).not.toBeInTheDocument();
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
