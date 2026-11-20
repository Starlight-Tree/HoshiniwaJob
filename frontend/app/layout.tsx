import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';
import { THEME_INIT_SCRIPT } from '../src/lib/theme';
import './globals.css';

export const metadata: Metadata = {
  title: { default: '星庭ジョブ｜宇宙の植物園・ガーデンの求人', template: '%s｜星庭ジョブ' },
  description: '宇宙の植物園・ガーデンの求人を、雇用形態・エリア・乗り場・職種でさがせます。',
  other: { 'color-scheme': 'light dark' },
};

export const viewport: Viewport = { width: 'device-width', initialScale: 1 };

// サイドパネルとフッターは、画面のグループごとの layout.tsx にある（求人の画面は (site)、園の管理は garden）。ログイン・会員登録（(auth)）は、迷わないよう上の帯だけ
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // data-theme は描画前のスクリプトが付ける（サーバーの出力とは違うので、警告を止める）
    <html lang="ja" suppressHydrationWarning>
      <head>
        <script>{THEME_INIT_SCRIPT}</script>
      </head>
      <body>{children}</body>
    </html>
  );
}
