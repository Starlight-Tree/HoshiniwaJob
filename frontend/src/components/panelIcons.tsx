import type { ReactNode } from 'react';

/** 詳細パネルのボタンの線画（DocuNavi の資料パネルと同じ形。ライブラリは使わず、線だけの SVG）。名前は、アイコンを入れるボタン・リンクの側が持つ（ここは読み上げの対象にしない）。 */
function Line({ children }: { children: ReactNode }) {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

/** ×（閉じる）。 */
export function CloseIcon() {
  return (
    <Line>
      <path d="M5 5l10 10M15 5L5 15" />
    </Line>
  );
}

/** 外向きの 4 つの矢印（拡大）。 */
export function ExpandIcon() {
  return (
    <Line>
      <path d="M11.5 3.5h5v5M16.5 3.5l-5.5 5.5M8.5 16.5h-5v-5M3.5 16.5l5.5-5.5" />
    </Line>
  );
}

/** 内向きの 4 つの矢印（縮小）。 */
export function CollapseIcon() {
  return (
    <Line>
      <path d="M16.5 8.5h-5v-5M11.5 8.5l5-5M3.5 11.5h5v5M8.5 11.5l-5 5" />
    </Line>
  );
}

/** 四角から出る矢印（ページで開く）。 */
export function OpenPageIcon() {
  return (
    <Line>
      <path d="M8.5 4.5H5a1 1 0 0 0-1 1V15a1 1 0 0 0 1 1h9.5a1 1 0 0 0 1-1v-3.5M11.5 3.5h5v5M16.5 3.5l-6 6" />
    </Line>
  );
}
