'use client';

import { useEffect, useId, useRef, useState } from 'react';

type Props = { name: string; email: string; logout: () => Promise<void>; honorific?: string };

/** ヘッダーのアカウントのメニュー。名前・メールアドレス・ログアウト。外を押す・Esc で閉じる。敬称は、利用者は「さん」、園は「御中」。 */
export function AccountMenu({ name, email, logout, honorific = 'さん' }: Props) {
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
          <p className="account-name">
            {name} {honorific}
          </p>
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
