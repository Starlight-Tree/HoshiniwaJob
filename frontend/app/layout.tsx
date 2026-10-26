import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';
import './globals.css';

export const metadata: Metadata = {
  title: { default: '星庭ジョブ｜宇宙の植物園・ガーデンの求人', template: '%s｜星庭ジョブ' },
  description: '宇宙の植物園・ガーデンの求人を、雇用形態・エリア・乗り場・職種でさがせます。',
};

export const viewport: Viewport = { width: 'device-width', initialScale: 1 };

// ヘッダーは、画面のグループごとの layout.tsx にある（求人の画面は (site)、ログイン・会員登録は (auth)）
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ja">
      <body>
        {children}
        <footer className="site-footer">
          <div className="inner">
            <p>表示している求人・法人名は、すべて練習用の架空のデータです。</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
