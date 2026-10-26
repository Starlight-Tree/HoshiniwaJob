import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // 開発サーバーを 127.0.0.1 で開いても、ブラウザーへの資産の配信が止まらないようにする
  allowedDevOrigins: ['127.0.0.1'],
  // `next dev` が AGENTS.md を自動で作るのを止める
  agentRules: false,
  // 開発サーバーが、サーバーアクションの引数（メール・名前など）を端末に出すのを止める
  logging: { serverFunctions: false },
};

export default nextConfig;
