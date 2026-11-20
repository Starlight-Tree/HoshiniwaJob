import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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

const { gardenLoginAction, gardenLogoutAction } = await import('./garden');

const form = (fields: Record<string, string>) => {
  const f = new FormData();
  for (const [k, v] of Object.entries(fields)) f.set(k, v);
  return f;
};
const reply = (status: number, body?: unknown) =>
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(body === undefined ? null : JSON.stringify(body), { status }));
const session = { token: 'garden-tok', garden: { id: 1, email: 'garden@example.com', corporate: '環軌道植物公社' } };

beforeEach(() => store.clear());
afterEach(() => vi.restoreAllMocks());

describe('gardenLoginAction', () => {
  it('成功したら園の Cookie だけを作り、/garden へ移す。利用者の Cookie は作らない', async () => {
    const fetchMock = reply(200, session);
    await expect(gardenLoginAction({}, form({ email: ' garden@example.com ', password: 'pw-pw-pw-1' }))).rejects.toMatchObject({ to: '/garden' });
    expect(store.get('hj_garden_session')?.value).toBe('garden-tok');
    expect(store.get('hj_garden_session')?.options).toMatchObject({ httpOnly: true, sameSite: 'lax', path: '/' });
    expect([...store.keys()].filter((name) => name.includes('jobnavi.'))).toEqual([]); // 求職者（Better Auth）の Cookie は作らない
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain('/api/garden/auth/login');
    expect(JSON.parse(String(init?.body))).toEqual({ email: 'garden@example.com', password: 'pw-pw-pw-1' });
  });

  // setToken が sessionCookieSecure() の結果を Cookie の secure に渡す配線を守る（判定そのものは cookie-secure.test.ts）
  it.each([
    ['production', undefined, true],
    ['production', 'false', false],
    ['development', undefined, false],
    ['development', 'true', true],
  ] as const)('NODE_ENV=%s・SESSION_COOKIE_SECURE=%s のとき、園の Cookie の secure は %s', async (nodeEnv, flag, expected) => {
    vi.stubEnv('NODE_ENV', nodeEnv);
    vi.stubEnv('SESSION_COOKIE_SECURE', flag as string);
    reply(200, session);
    try {
      await expect(gardenLoginAction({}, form({ email: 'garden@example.com', password: 'pw-pw-pw-1' }))).rejects.toMatchObject({ to: '/garden' });
      expect(store.get('hj_garden_session')?.options?.secure).toBe(expected);
    } finally {
      vi.unstubAllEnvs();
    }
  });

  it('401 は固定の文を返し、Cookie は作らない。入力したメールは残し、パスワードは返さない', async () => {
    reply(401, { detail: 'メールアドレスまたはパスワードが違います' });
    const state = await gardenLoginAction({}, form({ email: 'garden@example.com', password: 'wrong-pw' }));
    expect(state.error).toBe('メールアドレスまたはパスワードが違います');
    expect(state.values).toEqual({ email: 'garden@example.com' });
    expect(JSON.stringify(state)).not.toContain('wrong-pw');
    expect(store.size).toBe(0);
  });

  it('形式の誤りは、API を呼ばずに返す', async () => {
    const fetchMock = reply(200, session);
    const state = await gardenLoginAction({}, form({ email: 'nope', password: '' }));
    expect(state.fieldErrors?.email).toBeDefined();
    expect(state.fieldErrors?.password).toBeDefined();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('API に届かないときは、例外の文字列を出さず固定の文にする', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('connect ECONNREFUSED 10.0.0.5:8000'));
    const state = await gardenLoginAction({}, form({ email: 'garden@example.com', password: 'pw-pw-pw-1' }));
    expect(state.error).toBe('ただいま利用できません。しばらくしてから、もう一度お試しください');
    expect(JSON.stringify(state)).not.toContain('ECONNREFUSED');
  });
});

describe('gardenLogoutAction', () => {
  it('園のトークンを無効にして園の Cookie だけを消し、/garden/login へ移す', async () => {
    store.set('hj_garden_session', { value: 'garden-tok' });
    store.set('jobnavi.session_token', { value: 'user-tok' });
    const fetchMock = reply(204);
    await expect(gardenLogoutAction()).rejects.toMatchObject({ to: '/garden/login' });
    expect(store.has('hj_garden_session')).toBe(false);
    expect(store.get('jobnavi.session_token')?.value).toBe('user-tok');
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain('/api/garden/auth/logout');
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer garden-tok');
  });

  it('API に届かなくても、Cookie は消す', async () => {
    store.set('hj_garden_session', { value: 'garden-tok' });
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('down'));
    await expect(gardenLogoutAction()).rejects.toMatchObject({ to: '/garden/login' });
    expect(store.has('hj_garden_session')).toBe(false);
  });
});
