// 画面（Next.js）が返すセキュリティヘッダー。next.config.ts の headers() から呼ぶ。
// 純関数にしておくのは、設定ファイルを読み込まずに、中身を vitest で確かめられるようにするため。

export type SecurityHeader = { key: string; value: string };

// Content-Security-Policy（本番だけ）。
// script-src に 'unsafe-inline' が要る理由: Next.js の App Router は、nonce を使わないと、RSC の転送（flight データ）を
// inline のスクリプトで埋め込む。テーマの描画前のスクリプト（app/layout.tsx）も inline。
// nonce 方式にすると、全ページが動的な描画になり、静的な出力と CDN のキャッシュを失うので、ここでは採らない。
// それでも、外部ドメインのスクリプトの読み込み・object・フレームへの埋め込み・base の差し替えは止まる。
// 'unsafe-eval' は付けない（eval を使うのは、開発の React の refresh だけ）。
// img-src の https: は、Google のアバター（AccountMenu の生の <img>。lh3.googleusercontent.com など）と、
// R2 の公開画像（園の画像管理の生の <img>）が、別のホストから来るため。blob: は画像アップロードのプレビュー用。
// form-action は付けない: Google ログインのサーバーアクションが、外部（Google）への遷移をたどるので、
// Chrome がリダイレクト先を塞ぐ恐れがある。
// 開発（next dev）は React の refresh が eval を使うので、CSP は付けない。
const CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "frame-ancestors 'none'",
].join('; ');

export function securityHeaders(opts: { production: boolean }): SecurityHeader[] {
  // どの環境でも付けるもの（開発の動作を妨げない）
  const headers: SecurityHeader[] = [
    // Content-Type の推測（MIME スニッフィング）を止める
    { key: 'X-Content-Type-Options', value: 'nosniff' },
    // 別のサイトへは、オリジン（パスなし）だけを渡す。求人や園の URL の中身を外へ漏らさない
    { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
    // フレームへの埋め込みを禁じる（クリックジャッキング対策。CSP の frame-ancestors を解さない古いブラウザー向けの備えも兼ねる）
    { key: 'X-Frame-Options', value: 'DENY' },
    // 使わない機能は、閉じておく
    { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), payment=(), usb=()' },
  ];
  if (opts.production) {
    // https で配るのは本番だけ。ローカル（http://localhost）に付けても、ブラウザーは無視するが、意味が無い。
    // includeSubDomains は付けない: 同じ親ドメインの別のサービスまで、https を強いてしまうため
    headers.push({ key: 'Strict-Transport-Security', value: 'max-age=31536000' });
    headers.push({ key: 'Content-Security-Policy', value: CONTENT_SECURITY_POLICY });
  }
  return headers;
}
