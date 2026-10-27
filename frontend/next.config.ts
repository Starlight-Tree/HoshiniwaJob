import type { NextConfig } from 'next';

// 公開画像の URL の頭。本番は CDN の独自ドメイン（https://…）、ローカル保存の開発は /media（API が配る）。
const publicBase = process.env.IMAGE_PUBLIC_BASE_URL ?? '/media';
const publicUrl = /^https?:\/\//.test(publicBase) ? new URL(publicBase) : null;
// 外部画像の許可は、自分たちの配信元（ホスト）と、画像のパス（images/）だけに限る
const remotePatterns = publicUrl
  ? [
      {
        protocol: publicUrl.protocol.replace(':', '') as 'http' | 'https',
        hostname: publicUrl.hostname,
        port: publicUrl.port,
        pathname: `${publicUrl.pathname.replace(/\/$/, '')}/images/**`,
      },
    ]
  : [];

const nextConfig: NextConfig = {
  // 開発サーバーを 127.0.0.1 や host.docker.internal（開発コンテナのブラウザーから）で開いても、ブラウザーへの資産の配信が止まらないようにする
  allowedDevOrigins: ['127.0.0.1', 'host.docker.internal'],
  // `next dev` が AGENTS.md を自動で作るのを止める
  agentRules: false,
  // 開発サーバーが、サーバーアクションの引数（メール・名前など）を端末に出すのを止める
  logging: { serverFunctions: false },
  // 画像は JPEG などで置き、ブラウザーが対応していれば AVIF、次に WebP で配信する。求人の画像は API が返す公開 URL から取る
  images: { formats: ['image/avif', 'image/webp'], remotePatterns },
  // 園の画像のアップロード（サーバーアクション）の本文の上限。API 側の上限（既定 5MB）より少し大きくしておく
  experimental: { serverActions: { bodySizeLimit: '6mb' } },
  // ローカル保存のときだけ、/media を API へ渡す（ブラウザーと next/image の取得の両方が、同じ画面のオリジンで済む）
  async rewrites() {
    if (publicUrl) return [];
    const api = (process.env.API_BASE_URL ?? 'http://localhost:8000').replace(/\/+$/, '');
    return [{ source: '/media/:path*', destination: `${api}/media/:path*` }];
  },
};

export default nextConfig;
