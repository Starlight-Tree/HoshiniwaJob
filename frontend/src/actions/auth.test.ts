import { beforeEach, describe, expect, it, vi } from 'vitest';

const revalidate = vi.hoisted(() => vi.fn());
vi.mock('next/cache', () => ({ revalidatePath: revalidate }));

const store = new Map<string, { value: string; options?: Record<string, unknown> }>();
vi.mock('next/headers', () => ({
  cookies: async () => ({
    get: (k: string) => (store.has(k) ? { name: k, value: store.get(k)!.value } : undefined),
    getAll: () => [...store.entries()].map(([name, c]) => ({ name, value: c.value })),
    set: (k: string, value: string, options?: Record<string, unknown>) => void store.set(k, { value, options }),
    delete: (k: string) => void store.delete(k),
  }),
  headers: async () => new Headers({ cookie: 'x=1' }),
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

// Better Auth は、本物を動かさない（DB・Google へつなげない）。サーバー側の関数だけを差し替える
const api = vi.hoisted(() => ({ signInSocial: vi.fn(), signOut: vi.fn(), getToken: vi.fn() }));
const authRef = vi.hoisted(() => ({ current: null as { api: typeof api } | null }));
vi.mock('../lib/auth', () => ({ getAuth: () => authRef.current }));
const token = vi.hoisted(() => ({ value: null as string | null }));
vi.mock('../lib/session', () => ({ userToken: async () => token.value }));

const { googleLoginAction, logoutAction, updateNameAction } = await import('./auth');

const form = (fields: Record<string, string>) => {
  const f = new FormData();
  for (const [k, v] of Object.entries(fields)) f.set(k, v);
  return f;
};
const reply = (status: number, body?: unknown) =>
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(body === undefined ? null : JSON.stringify(body), { status }));

beforeEach(() => {
  store.clear();
  api.signInSocial.mockReset();
  api.signOut.mockReset();
  authRef.current = { api };
  token.value = null;
});

describe('googleLoginAction', () => {
  it('Google の同意画面の URL へ移す。失敗・取り消しの戻りはログイン画面にする', async () => {
    api.signInSocial.mockResolvedValue({ url: 'https://accounts.google.com/o/oauth2/v2/auth?x=1', redirect: true });
    await expect(googleLoginAction()).rejects.toMatchObject({ to: 'https://accounts.google.com/o/oauth2/v2/auth?x=1' });
    expect(api.signInSocial).toHaveBeenCalledOnce();
    expect(api.signInSocial.mock.calls[0]![0].body).toEqual({ provider: 'google', callbackURL: '/', errorCallbackURL: '/login' });
  });

  it('設定が足りないときは、Better Auth を呼ばずに、ログイン画面へ（まだ設定されていません）', async () => {
    authRef.current = null;
    await expect(googleLoginAction()).rejects.toMatchObject({ to: '/login?error=not_configured' });
    expect(api.signInSocial).not.toHaveBeenCalled();
  });

  it('Better Auth が失敗しても（URL が無い・例外）、例外の文字列を出さず、ログイン画面へ', async () => {
    api.signInSocial.mockRejectedValue(new Error('connect ECONNREFUSED 10.0.0.5:5432'));
    await expect(googleLoginAction()).rejects.toMatchObject({ to: '/login?error=google_failed' });
    api.signInSocial.mockResolvedValue({ redirect: false });
    await expect(googleLoginAction()).rejects.toMatchObject({ to: '/login?error=google_failed' });
  });
});

describe('updateNameAction', () => {
  const loggedIn = () => (token.value = 'jwt-123');

  it('成功したら、JWT を付けて API に姓・名を送り、サイドパネルを更新する（保存できた印を返す）', async () => {
    loggedIn();
    const fetchMock = reply(200, { id: 1, email: 'a@example.com', last_name: '新姓', first_name: '新名' });
    const state = await updateNameAction({}, form({ last_name: ' 新姓 ', first_name: '新名' }));
    expect(state).toEqual({ saved: true, values: { last_name: '新姓', first_name: '新名' } });
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain('/api/auth/me');
    expect(init?.method).toBe('PATCH');
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer jwt-123');
    expect(JSON.parse(String(init?.body))).toEqual({ last_name: '新姓', first_name: '新名' });
    expect(revalidate).toHaveBeenCalledWith('/', 'layout');
  });

  it('空・長すぎる入力は、API を呼ばずに返す', async () => {
    loggedIn();
    const fetchMock = reply(200, {});
    const state = await updateNameAction({}, form({ last_name: '', first_name: 'x'.repeat(51) }));
    expect(state.fieldErrors?.last_name).toBeDefined();
    expect(state.fieldErrors?.first_name).toBeDefined();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('ログインしていなければ（JWT が取れない）、API を呼ばない', async () => {
    const fetchMock = reply(200, {});
    const state = await updateNameAction({}, form({ last_name: '姓', first_name: '名' }));
    expect(state.error).toContain('有効期限');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('API が 401（期限切れ）なら、そのことを伝える。ほかの失敗は固定の文で、例外の文字列を出さない', async () => {
    loggedIn();
    reply(401, { detail: 'ログインしてください' });
    expect((await updateNameAction({}, form({ last_name: '姓', first_name: '名' }))).error).toContain('有効期限');
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('connect ECONNREFUSED 10.0.0.5:8000'));
    const state = await updateNameAction({}, form({ last_name: '姓', first_name: '名' }));
    expect(state.error).toBe('ただいま利用できません。しばらくしてから、もう一度お試しください');
    expect(JSON.stringify(state)).not.toContain('ECONNREFUSED');
  });
});

describe('logoutAction', () => {
  it('Better Auth でサーバー側の印を消し、/ へ移す', async () => {
    api.signOut.mockResolvedValue({ success: true });
    await expect(logoutAction()).rejects.toMatchObject({ to: '/' });
    expect(api.signOut).toHaveBeenCalledOnce();
  });

  it('Better Auth に届かなくても、この端末の Better Auth の Cookie だけは消す（園の Cookie・他のアプリの Cookie は残す）', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    store.set('hoshiniwajob.session_token', { value: 'x' });
    store.set('__Secure-hoshiniwajob.session_token', { value: 'y' });
    store.set('better-auth.session_token', { value: 'docunavi' }); // 同じ localhost の別のアプリ（接頭辞が違う）
    store.set('hj_garden_session', { value: 'garden-tok' });
    api.signOut.mockRejectedValue(new Error('down'));
    await expect(logoutAction()).rejects.toMatchObject({ to: '/' });
    // 期限切れにして上書きする。https の Cookie は、Secure を付けないと、ブラウザーが消させない
    expect(store.get('hoshiniwajob.session_token')).toMatchObject({ value: '', options: { maxAge: 0, secure: false } });
    expect(store.get('__Secure-hoshiniwajob.session_token')).toMatchObject({ value: '', options: { maxAge: 0, secure: true } });
    expect(store.get('better-auth.session_token')?.value).toBe('docunavi');
    expect(store.get('hj_garden_session')?.value).toBe('garden-tok');
  });
});
