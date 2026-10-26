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

const { loginAction, logoutAction, registerAction } = await import('./auth');

const form = (fields: Record<string, string>) => {
  const f = new FormData();
  for (const [k, v] of Object.entries(fields)) f.set(k, v);
  return f;
};
const reply = (status: number, body?: unknown) =>
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(body === undefined ? null : JSON.stringify(body), { status }));
const session = { token: 'tok-123', user: { id: 1, email: 'a@example.com', last_name: '試験', first_name: '花子' } };

beforeEach(() => store.clear());

describe('loginAction', () => {
  it('成功したらトークンを HttpOnly の Cookie に入れて / へ移す', async () => {
    const fetchMock = reply(200, session);
    await expect(loginAction({}, form({ email: ' a@example.com ', password: 'pw-pw-pw-1' }))).rejects.toMatchObject({ to: '/' });
    expect(store.get('hj_session')?.value).toBe('tok-123');
    expect(store.get('hj_session')?.options).toMatchObject({ httpOnly: true, sameSite: 'lax', path: '/' });
    const [, init] = fetchMock.mock.calls[0]!;
    expect(JSON.parse(String(init?.body))).toEqual({ email: 'a@example.com', password: 'pw-pw-pw-1' });
    expect(store.has('hj_registered')).toBe(false);
  });

  it('401 は固定の文を返し、Cookie は作らない。入力したメールは残す', async () => {
    reply(401, { detail: 'メールアドレスまたはパスワードが違います' });
    const state = await loginAction({}, form({ email: 'a@example.com', password: 'wrong-pw' }));
    expect(state.error).toBe('メールアドレスまたはパスワードが違います');
    expect(state.values).toEqual({ email: 'a@example.com' });
    expect(JSON.stringify(state)).not.toContain('wrong-pw');
    expect(store.size).toBe(0);
  });

  it('形式の誤りは、API を呼ばずに返す', async () => {
    const fetchMock = reply(200, session);
    const state = await loginAction({}, form({ email: 'nope', password: '' }));
    expect(state.fieldErrors?.email).toBeDefined();
    expect(state.fieldErrors?.password).toBeDefined();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('API に届かないときは、例外の文字列を出さず固定の文にする', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('connect ECONNREFUSED 10.0.0.5:8000'));
    const state = await loginAction({}, form({ email: 'a@example.com', password: 'pw-pw-pw-1' }));
    expect(state.error).toBe('ただいま利用できません。しばらくしてから、もう一度お試しください');
    expect(JSON.stringify(state)).not.toContain('ECONNREFUSED');
  });
});

describe('registerAction', () => {
  const input = { last_name: '試験', first_name: '花子', email: 'a@example.com', password: 'correct-horse-1' };

  it('成功したらログイン状態にし、完了メッセージの印を付けて / へ移す', async () => {
    reply(201, session);
    await expect(registerAction({}, form(input))).rejects.toMatchObject({ to: '/' });
    expect(store.get('hj_session')?.value).toBe('tok-123');
    expect(store.get('hj_registered')?.value).toBe('1');
    expect(store.get('hj_registered')?.options).toMatchObject({ maxAge: 60 });
  });

  it('409 は、ログイン失敗と同じ形（error）で固定の文を返す。パスワードは返さない', async () => {
    reply(409, { detail: 'このメールアドレスは登録できません' });
    const state = await registerAction({}, form(input));
    expect(state.error).toBe('このメールアドレスは登録できません');
    expect(state.values).toEqual({ last_name: '試験', first_name: '花子', email: 'a@example.com' });
    expect(JSON.stringify(state)).not.toContain('correct-horse-1');
    expect(store.size).toBe(0);
  });

  it('短いパスワードは、API を呼ばずに文字数つきで返す', async () => {
    const fetchMock = reply(201, session);
    const state = await registerAction({}, form({ ...input, password: 'abc123' }));
    expect(state.fieldErrors?.password).toContain('いま 6 文字');
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('logoutAction', () => {
  it('API のトークンを無効にして、Cookie を消し、/ へ移す', async () => {
    store.set('hj_session', { value: 'tok-123' });
    const fetchMock = reply(204);
    await expect(logoutAction()).rejects.toMatchObject({ to: '/' });
    expect(store.has('hj_session')).toBe(false);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain('/api/auth/logout');
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer tok-123');
  });

  it('API に届かなくても、Cookie は消す', async () => {
    store.set('hj_session', { value: 'tok-123' });
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('down'));
    await expect(logoutAction()).rejects.toMatchObject({ to: '/' });
    expect(store.has('hj_session')).toBe(false);
  });
});
