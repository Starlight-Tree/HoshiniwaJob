import { beforeEach, describe, expect, it, vi } from 'vitest';

const token = vi.hoisted(() => ({ value: null as string | null }));
vi.mock('../lib/session', () => ({ userToken: async () => token.value }));

const { recordViewAction } = await import('./recruit-events');

const reply = (status: number, body?: unknown) =>
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(body === undefined ? null : JSON.stringify(body), { status }));

beforeEach(() => {
  token.value = null;
});

describe('recordViewAction（閲覧の記録）', () => {
  it('ログイン中は、JWT を付けて、API に POST /api/recruits/ID/view を 1 回送る（何も返さない）', async () => {
    token.value = 'jwt-123';
    const fetchMock = reply(204);
    await expect(recordViewAction(7)).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toMatch(/\/api\/recruits\/7\/view$/);
    expect(init?.method).toBe('POST');
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer jwt-123');
  });

  it('ログインしていない（JWT が取れない）と、API を呼ばない（401 を出さない）', async () => {
    const fetchMock = reply(204);
    await expect(recordViewAction(7)).resolves.toBeUndefined();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([0, -1, 1.5, Number.NaN, '7', null, undefined])('求人の ID が正の整数でない（%j）と、API を呼ばない', async (id) => {
    token.value = 'jwt-123';
    const fetchMock = reply(204);
    await expect(recordViewAction(id as number)).resolves.toBeUndefined();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([401, 404, 500])('API が %i を返しても、例外を投げない（記録は付随。何も変えない）', async (status) => {
    token.value = 'jwt-123';
    reply(status, { detail: 'x' });
    await expect(recordViewAction(7)).resolves.toBeUndefined();
  });

  it('API に接続できなくても、例外を投げない', async () => {
    token.value = 'jwt-123';
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('connect ECONNREFUSED 10.0.0.5:8000'));
    await expect(recordViewAction(7)).resolves.toBeUndefined();
  });
});
