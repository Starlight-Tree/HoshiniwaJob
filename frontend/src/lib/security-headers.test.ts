import { describe, expect, it } from 'vitest';
import { securityHeaders } from './security-headers';

function valueOf(headers: { key: string; value: string }[], key: string) {
  return headers.find((h) => h.key === key)?.value;
}

describe('セキュリティヘッダー', () => {
  it('開発では、CSP と HSTS を付けない（React の refresh が eval を使い、http で配るため）', () => {
    const headers = securityHeaders({ production: false });
    expect(valueOf(headers, 'Content-Security-Policy')).toBeUndefined();
    expect(valueOf(headers, 'Strict-Transport-Security')).toBeUndefined();
  });

  it.each([false, true])('どの環境でも、常に付けるヘッダーが付く（production: %s）', (production) => {
    const headers = securityHeaders({ production });
    expect(valueOf(headers, 'X-Content-Type-Options')).toBe('nosniff');
    expect(valueOf(headers, 'Referrer-Policy')).toBe('strict-origin-when-cross-origin');
    expect(valueOf(headers, 'X-Frame-Options')).toBe('DENY');
    expect(valueOf(headers, 'Permissions-Policy')).toBe('camera=(), microphone=(), geolocation=(), payment=(), usb=()');
  });

  it('本番では、CSP と HSTS が付く（HSTS は includeSubDomains なし）', () => {
    const headers = securityHeaders({ production: true });
    expect(valueOf(headers, 'Strict-Transport-Security')).toBe('max-age=31536000');
    expect(valueOf(headers, 'Content-Security-Policy')).toBeTruthy();
  });

  it('本番の CSP は、eval を許さず、フレームの埋め込み・object・base の差し替えを止める', () => {
    const csp = valueOf(securityHeaders({ production: true }), 'Content-Security-Policy') ?? '';
    const directives = csp.split('; ');
    expect(csp).not.toContain("'unsafe-eval'");
    expect(directives).toContain("frame-ancestors 'none'");
    expect(directives).toContain("object-src 'none'");
    expect(directives).toContain("base-uri 'self'");
    expect(directives).toContain("default-src 'self'");
  });

  it('本番の CSP は、Google のログインの遷移を塞がない（form-action を付けない）', () => {
    const csp = valueOf(securityHeaders({ production: true }), 'Content-Security-Policy') ?? '';
    expect(csp).not.toContain('form-action');
  });

  it.each([false, true])('同じヘッダー名を重複させない（production: %s）', (production) => {
    const names = securityHeaders({ production }).map((h) => h.key.toLowerCase());
    expect(new Set(names).size).toBe(names.length);
  });
});
