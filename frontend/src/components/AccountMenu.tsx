'use client';

import Link from 'next/link';
import { useEffect, useId, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { chooseTheme, clearTheme, themeChoice } from '../lib/theme';
import type { Theme } from '../lib/theme';
import { PersonIcon } from './icons';
import { THEME_OPTIONS } from './themeOptions';

type Props = {
  /** ログイン中の表示名。渡さなければ、ログインしていない人のメニュー（テーマと、`loginHref` があればログインの入口）。 */
  name?: string;
  email?: string;
  logout?: () => Promise<void>;
  /** 敬称は、利用者は「さん」、園は「御中」。 */
  honorific?: string;
  /** ログインしていない人のメニューに出す、ログイン・会員登録の行き先。 */
  loginHref?: string;
};

/**
 * サイドパネル下部のアカウント（DocuNavi と同じ形）。アバターのボタンを押すと、メニューが開く。
 * ログイン中は、名前・メールアドレス・テーマ（ライト / ダーク / システム）・ログアウト。ログインしていなければ、テーマと、ログインの入口。
 * 開いたら先頭の項目にフォーカスを置く。↑↓ で移動、Esc で閉じてボタンへ戻る。メニューの外を押しても閉じる。
 * テーマを選ぶと localStorage に保存し、以後は OS より優先する（「システム」で OS に従う状態へ戻す）。保存値は、開いたときに読む（サーバーの出力とずれないよう、描画の最初には読まない）。
 */
export function AccountMenu({ name, email, logout, honorific = 'さん', loginHref }: Props) {
  const signedIn = name !== undefined && email !== undefined && logout !== undefined;
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<Theme | 'system'>('system');
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    setTheme(themeChoice());
    menuRef.current?.querySelector<HTMLElement>('[role^="menuitem"]')?.focus();
    const onPointer = (event: MouseEvent) => {
      const node = event.target as Node;
      if (!menuRef.current?.contains(node) && !buttonRef.current?.contains(node)) setOpen(false);
    };
    document.addEventListener('mousedown', onPointer);
    return () => document.removeEventListener('mousedown', onPointer);
  }, [open]);

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const items = [...(menuRef.current?.querySelectorAll<HTMLElement>('[role^="menuitem"]') ?? [])];
    const index = items.findIndex((node) => node === document.activeElement);
    if (event.key === 'Escape') {
      event.preventDefault();
      setOpen(false);
      buttonRef.current?.focus();
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      items[(index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus();
    } else if (event.key === 'Tab') {
      setOpen(false);
    }
  };

  return (
    <div className="account">
      {open ? (
        <div ref={menuRef} id={menuId} role="menu" aria-label={signedIn ? 'アカウント' : 'メニュー'} className="account-menu" onKeyDown={handleKeyDown}>
          {signedIn ? (
            <div className="account-who">
              <p className="account-name">
                {name} {honorific}
              </p>
              <p className="account-email">{email}</p>
            </div>
          ) : null}
          <div role="group" aria-label="テーマ" className="account-theme">
            <span className="account-theme-label" aria-hidden="true">
              テーマ
            </span>
            <span className="account-theme-options">
              {THEME_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  role="menuitemradio"
                  aria-checked={theme === option.value}
                  aria-label={option.label}
                  title={option.label}
                  className="account-theme-option"
                  onClick={() => {
                    if (option.value === 'system') clearTheme();
                    else chooseTheme(option.value);
                    setTheme(option.value);
                  }}
                >
                  {option.icon}
                </button>
              ))}
            </span>
          </div>
          {signedIn ? (
            <form action={logout}>
              <button type="submit" role="menuitem" className="account-item">
                ログアウト
              </button>
            </form>
          ) : loginHref ? (
            <Link href={loginHref} role="menuitem" className="account-item" onClick={() => setOpen(false)}>
              ログイン・会員登録
            </Link>
          ) : null}
        </div>
      ) : null}
      <button
        ref={buttonRef}
        type="button"
        className="account-button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={signedIn ? `${name}のアカウントメニュー` : 'メニュー'}
        data-tip={signedIn ? 'アカウントメニュー' : 'メニュー'}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="account-avatar" aria-hidden="true">
          {signedIn ? <PersonIcon /> : '≡'}
        </span>
      </button>
    </div>
  );
}
