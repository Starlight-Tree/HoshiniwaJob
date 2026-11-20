import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  authorizationUrl,
  challengeOf,
  googleConfig,
  googleErrorCodeFor,
  googleErrorMessage,
  newOAuthState,
  parseOAuthState,
  sameValue,
} from './google';

afterEach(() => vi.unstubAllEnvs());

describe('PKCE・state・nonce', () => {
  it('RFC 7636 の例のとおりに、verifier から S256 の challenge を作る', () => {
    expect(challengeOf('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk')).toBe('E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM');
  });

  it('毎回違う値を作り、verifier は 43〜128 文字の URL に安全な文字だけ', () => {
    const a = newOAuthState();
    const b = newOAuthState();
    expect(a.state).not.toBe(b.state);
    expect(a.nonce).not.toBe(b.nonce);
    expect(a.verifier).not.toBe(b.verifier);
    expect(a.verifier.length).toBeGreaterThanOrEqual(43);
    expect(a.verifier.length).toBeLessThanOrEqual(128);
    for (const v of [a.state, a.nonce, a.verifier]) expect(v).toMatch(/^[A-Za-z0-9_-]+$/);
  });

  it('Cookie の値は、形が正しいときだけ読む', () => {
    const s = newOAuthState();
    expect(parseOAuthState(JSON.stringify(s))).toEqual(s);
    for (const bad of [undefined, '', 'not json', '{}', JSON.stringify({ state: 1, nonce: 'n', verifier: 'v' }), JSON.stringify({ state: 's', nonce: 'n' })]) {
      expect(parseOAuthState(bad)).toBeNull();
    }
  });

  it('同じ値だけを同じとする（長さが違っても例外にしない）', () => {
    expect(sameValue('abc', 'abc')).toBe(true);
    expect(sameValue('abc', 'abd')).toBe(false);
    expect(sameValue('abc', 'abcd')).toBe(false);
    expect(sameValue('', 'x')).toBe(false);
  });
});

describe('設定と同意画面の URL', () => {
  it('クライアント ID が無ければ null。戻り先の既定はローカルの画面', () => {
    vi.stubEnv('GOOGLE_CLIENT_ID', '');
    expect(googleConfig()).toBeNull();
    vi.stubEnv('GOOGLE_CLIENT_ID', ' cid ');
    vi.stubEnv('GOOGLE_REDIRECT_URI', '');
    expect(googleConfig()).toEqual({ clientId: 'cid', redirectUri: 'http://localhost:3200/auth/google/callback' });
  });

  it('同意画面の URL に、code・state・nonce・PKCE（S256）・openid の範囲を付け、シークレットは付けない', () => {
    const s = newOAuthState();
    const url = new URL(authorizationUrl({ clientId: 'cid', redirectUri: 'http://localhost:3200/auth/google/callback' }, s));
    expect(`${url.origin}${url.pathname}`).toBe('https://accounts.google.com/o/oauth2/v2/auth');
    const q = url.searchParams;
    expect(q.get('client_id')).toBe('cid');
    expect(q.get('redirect_uri')).toBe('http://localhost:3200/auth/google/callback');
    expect(q.get('response_type')).toBe('code');
    expect(q.get('scope')).toBe('openid email profile');
    expect(q.get('state')).toBe(s.state);
    expect(q.get('nonce')).toBe(s.nonce);
    expect(q.get('code_challenge')).toBe(challengeOf(s.verifier));
    expect(q.get('code_challenge_method')).toBe('S256');
    expect(url.toString()).not.toContain(s.verifier);
    expect(url.toString().toLowerCase()).not.toContain('secret');
  });
});

describe('ログイン画面に出す文', () => {
  it('URL のコードが決まったものだけ、固定の文にする。それ以外（自由な文字）は出さない', () => {
    expect(googleErrorMessage('google_failed')).toContain('失敗');
    expect(googleErrorMessage('google_conflict')).toContain('別の Google アカウント');
    expect(googleErrorMessage('google_unconfigured')).toContain('設定されていません');
    expect(googleErrorMessage('<script>alert(1)</script>')).toBeNull();
    expect(googleErrorMessage('constructor')).toBeNull();
    expect(googleErrorMessage(undefined)).toBeNull();
  });

  it('API の状態から、コードを決める', () => {
    expect(googleErrorCodeFor(503)).toBe('google_unconfigured');
    expect(googleErrorCodeFor(409)).toBe('google_conflict');
    for (const status of [0, 400, 401, 422, 500]) expect(googleErrorCodeFor(status)).toBe('google_failed');
  });
});
