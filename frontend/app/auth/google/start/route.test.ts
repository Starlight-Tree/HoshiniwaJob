import { beforeEach, describe, expect, it, vi } from 'vitest';

const store = new Map<string, { value: string; options?: Record<string, unknown> }>();
vi.mock('next/headers', () => ({
  cookies: async () => ({
    get: (k: string) => (store.has(k) ? { name: k, value: store.get(k)!.value } : undefined),
    set: (k: string, value: string, options?: Record<string, unknown>) => void store.set(k, { value, options }),
    delete: (k: string) => void store.delete(k),
  }),
}));
class Redirected extends Error {
  constructor(readonly to: string) {
    super(to);
  }
}
vi.mock('next/navigation', () => ({
  redirect: (to: string) => {
    throw new Redirected(to);
  },
}));

const { GET } = await import('./route');
const { challengeOf } = await import('../../../../src/lib/google');

beforeEach(() => {
  store.clear();
  vi.unstubAllEnvs();
});

describe('GET /auth/google/start', () => {
  it('クライアント ID が無ければ、Cookie を作らず、ログイン画面へ（未設定）', async () => {
    vi.stubEnv('GOOGLE_CLIENT_ID', '');
    await expect(GET()).rejects.toMatchObject({ to: '/login?error=google_unconfigured' });
    expect(store.size).toBe(0);
  });

  it('state・nonce・verifier を HttpOnly の短い Cookie に持ち、Google の同意画面へ送る', async () => {
    vi.stubEnv('GOOGLE_CLIENT_ID', 'cid');
    vi.stubEnv('GOOGLE_REDIRECT_URI', 'http://localhost:3200/auth/google/callback');
    const err = (await GET().catch((e: unknown) => e)) as Redirected;
    const url = new URL(err.to);
    expect(url.origin).toBe('https://accounts.google.com');

    const cookie = store.get('hj_oauth')!;
    expect(cookie.options).toMatchObject({ httpOnly: true, sameSite: 'lax', path: '/auth/google', maxAge: 600 });
    const saved = JSON.parse(cookie.value) as { state: string; nonce: string; verifier: string };
    expect(url.searchParams.get('state')).toBe(saved.state);
    expect(url.searchParams.get('nonce')).toBe(saved.nonce);
    expect(url.searchParams.get('code_challenge')).toBe(challengeOf(saved.verifier));
    expect(err.to).not.toContain(saved.verifier); // verifier は、同意画面の URL には出さない（チャレンジだけ）
  });

  it('https で公開するとき（SESSION_COOKIE_SECURE=true）は、Cookie に Secure を付ける', async () => {
    vi.stubEnv('GOOGLE_CLIENT_ID', 'cid');
    vi.stubEnv('SESSION_COOKIE_SECURE', 'true');
    await GET().catch(() => undefined);
    expect(store.get('hj_oauth')?.options).toMatchObject({ secure: true });
  });
});
