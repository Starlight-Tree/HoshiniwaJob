'use client';

import { useEffect, useRef, useState } from 'react';

const COOKIE = 'hj_registered';

/** 会員登録の直後に 1 回だけ出す「完了しました」。印の Cookie を読んだらすぐ消すので、再読み込み・戻るでは出ない。 */
export function RegisteredNotice() {
  const [open, setOpen] = useState(false);
  const checked = useRef(false); // 開発時の二重実行で、印を消したあとに読み直さないため

  useEffect(() => {
    if (checked.current) return;
    checked.current = true;
    if (document.cookie.split('; ').some((c) => c === `${COOKIE}=1`)) {
      document.cookie = `${COOKIE}=; Max-Age=0; path=/`;
      setOpen(true);
    }
  }, []);

  if (!open) return null;
  return (
    <div className="flash" role="status">
      <p>会員登録が完了しました</p>
      <button type="button" aria-label="メッセージを閉じる" onClick={() => setOpen(false)}>
        ×
      </button>
    </div>
  );
}
