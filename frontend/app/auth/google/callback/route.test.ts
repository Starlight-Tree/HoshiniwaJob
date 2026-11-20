import { beforeEach, describe, expect, it, vi } from 'vitest';

const store = new Map<string, { value: string; options?: Record<string, unknown> }>();
const deleted: Array<unknown> = [];
vi.mock('next/headers', () => ({
  cookies: async () => ({
    get: (k: string) => (store.has(k) ? { name: k, value: store.get(k)!.value } : undefined),
    set: (k: string, value: string, options?: Record<string, unknown>) => void store.set(k, { value, options }),
    delete: (arg: string | { name: string }) => {
      deleted.push(arg);
      store.delete(typeof arg === 'string' ? arg : arg.name);
    },
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

const SAVED = { state: 'state-ok', nonce: 'n'.repeat(32), verifier: 'v'.repeat(60) };
const request = (query: string) => new Request(`http://localhost:3200/auth/google/callback?${query}`);
const goes = async (query: string) => ((await GET(request(query)).catch((e: unknown) => e)) as Redirected).to;
const reply = (status: number, body?: unknown) =>
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(body === undefined ? null : JSON.stringify(body), { status }));

beforeEach(() => {
  store.clear();
  deleted.length = 0;
  vi.unstubAllEnvs();
  vi.stubEnv('GOOGLE_CLIENT_ID', 'cid');
  vi.stubEnv('GOOGLE_REDIRECT_URI', 'http://localhost:3200/auth/google/callback');
  store.set('hj_oauth', { value: JSON.stringify(SAVED) });
});

describe('GET /auth/google/callback', () => {
  it('成功: state が合えば、code・verifier・nonce・戻り先を API に渡し、トークンを HttpOnly の Cookie に入れて / へ', async () => {
    const fetchMock = reply(200, { token: 'tok-google', user: { id: 1, email: 'a@example.com', last_name: null, first_name: null } });
    expect(await goes('code=abc&state=state-ok')).toBe('/');
    expect(store.get('hj_session')?.value).toBe('tok-google');
    expect(store.get('hj_session')?.options).toMatchObject({ httpOnly: true, sameSite: 'lax', path: '/' });
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain('/api/auth/google');
    expect(JSON.parse(String(init?.body))).toEqual({
      code: 'abc',
      code_verifier: SAVED.verifier,
      nonce: SAVED.nonce,
      redirect_uri: 'http://localhost:3200/auth/google/callback',
    });
  });

  it('1 回で使い切る: 照合のあと、一時の Cookie は（path つきで）消す', async () => {
    reply(200, { token: 't', user: {} });
    await goes('code=abc&state=state-ok');
    expect(deleted).toContainEqual({ name: 'hj_oauth', path: '/auth/google' });
    expect(store.has('hj_oauth')).toBe(false);
  });

  it.each([
    ['state が違う', 'code=abc&state=other'],
    ['state が無い', 'code=abc'],
    ['code が無い', 'state=state-ok'],
    ['Google が拒否した（error）', 'error=access_denied&state=state-ok'],
  ])('%s → API を呼ばず、ログインの印も作らず、失敗としてログイン画面へ', async (_name, query) => {
    const fetchMock = reply(200, { token: 'must-not-be-used' });
    expect(await goes(query)).toBe('/login?error=google_failed');
    expect(fetchMock).not.toHaveBeenCalled();
    expect(store.has('hj_session')).toBe(false);
  });

  it('一時の Cookie が無い（期限切れ・別の端末）なら、失敗', async () => {
    store.delete('hj_oauth');
    const fetchMock = reply(200, { token: 'x' });
    expect(await goes('code=abc&state=state-ok')).toBe('/login?error=google_failed');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('一時の Cookie が壊れていたら、失敗', async () => {
    store.set('hj_oauth', { value: '{broken' });
    expect(await goes('code=abc&state=state-ok')).toBe('/login?error=google_failed');
  });

  it('クライアント ID が無ければ、未設定', async () => {
    vi.stubEnv('GOOGLE_CLIENT_ID', '');
    expect(await goes('code=abc&state=state-ok')).toBe('/login?error=google_unconfigured');
  });

  it.each([
    [503, 'google_unconfigured'],
    [409, 'google_conflict'],
    [400, 'google_failed'],
    [500, 'google_failed'],
  ])('API が %i を返したら、コード %s で戻す（API の本文は URL にも出さない）', async (status, code) => {
    reply(status, { detail: 'secret detail from api' });
    const to = await goes('code=abc&state=state-ok');
    expect(to).toBe(`/login?error=${code}`);
    expect(to).not.toContain('secret');
    expect(store.has('hj_session')).toBe(false);
  });

  it('API に届かないときも、失敗として戻す（例外の文字列は出さない）', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('connect ECONNREFUSED 10.0.0.5:8000'));
    const to = await goes('code=abc&state=state-ok');
    expect(to).toBe('/login?error=google_failed');
    expect(to).not.toContain('ECONNREFUSED');
  });
});
