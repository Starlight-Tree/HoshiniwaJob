'use client';

import { useEffect, useId, useRef, useState } from 'react';

type Props = { name: string; email: string; logout: () => Promise<void> };

/** ヘッダーのアカウントのメニュー。名前・メールアドレス・ログアウト。外を押す・Esc で閉じる。 */
export function AccountMenu({ name, email, logout }: Props) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: MouseEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        button.current?.focus();
      }
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className="account" ref={root}>
      <button ref={button} type="button" className="account-button" aria-expanded={open} aria-controls={menuId} onClick={() => setOpen((v) => !v)}>
        {name} ▾
      </button>
      {open ? (
        <div id={menuId} className="account-menu">
          <p className="account-name">{name} さん</p>
          <p className="account-email">{email}</p>
          <form action={logout}>
            <button type="submit" className="logout-button">
              ログアウト
            </button>
          </form>
        </div>
      ) : null}
    </div>
  );
}
