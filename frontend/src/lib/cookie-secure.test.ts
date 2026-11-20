import { afterEach, describe, expect, it, vi } from 'vitest';
import { sessionCookieSecure } from './cookie-secure';

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('sessionCookieSecure', () => {
  it.each(['true', 'TRUE', 'True', ' true ', '\ttrue\n'])('SESSION_COOKIE_SECURE=%j は、どの NODE_ENV でも true', (flag) => {
    for (const NODE_ENV of ['production', 'development', 'test', undefined]) {
      expect(sessionCookieSecure({ SESSION_COOKIE_SECURE: flag, NODE_ENV })).toBe(true);
    }
  });

  it.each(['false', 'FALSE', ' false '])('SESSION_COOKIE_SECURE=%j は、本番でも false（http で本番ビルドを試すとき）', (flag) => {
    for (const NODE_ENV of ['production', 'development', 'test', undefined]) {
      expect(sessionCookieSecure({ SESSION_COOKIE_SECURE: flag, NODE_ENV })).toBe(false);
    }
  });

  it('未設定なら、本番だけ true（付け忘れても本番は secure になる）', () => {
    expect(sessionCookieSecure({ NODE_ENV: 'production' })).toBe(true);
    expect(sessionCookieSecure({ NODE_ENV: 'development' })).toBe(false);
    expect(sessionCookieSecure({ NODE_ENV: 'test' })).toBe(false);
    expect(sessionCookieSecure({})).toBe(false);
  });

  it.each(['1', '0', 'yes', 'no', 'on', 'off', 'secure', ''])('SESSION_COOKIE_SECURE=%j は、明示とみなさず NODE_ENV に従う', (flag) => {
    expect(sessionCookieSecure({ SESSION_COOKIE_SECURE: flag, NODE_ENV: 'production' })).toBe(true);
    expect(sessionCookieSecure({ SESSION_COOKIE_SECURE: flag, NODE_ENV: 'development' })).toBe(false);
    expect(sessionCookieSecure({ SESSION_COOKIE_SECURE: flag })).toBe(false);
  });

  it('NODE_ENV が production 以外の値でも、secure にはしない', () => {
    expect(sessionCookieSecure({ NODE_ENV: 'staging' })).toBe(false);
    expect(sessionCookieSecure({ NODE_ENV: 'Production' })).toBe(false);
  });

  it('引数を省くと process.env を読む', () => {
    vi.stubEnv('NODE_ENV', 'production');
    vi.stubEnv('SESSION_COOKIE_SECURE', undefined);
    expect(sessionCookieSecure()).toBe(true);
    vi.stubEnv('SESSION_COOKIE_SECURE', 'false');
    expect(sessionCookieSecure()).toBe(false);
    vi.stubEnv('NODE_ENV', 'development');
    vi.stubEnv('SESSION_COOKIE_SECURE', 'true');
    expect(sessionCookieSecure()).toBe(true);
  });
});
