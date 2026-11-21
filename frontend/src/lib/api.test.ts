import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, fetchRecommendations, fetchRelatedRecruits, recordRecruitView } from './api';

// 関連する求人・おすすめ・閲覧の記録の呼び出し。fetch を差し替える（実 API・ネットワークは呼ばない）
const reply = (status: number, body?: unknown) =>
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(body === undefined ? null : JSON.stringify(body), { status }));

afterEach(() => vi.unstubAllEnvs());

describe('fetchRelatedRecruits', () => {
  it('公開 API を GET で呼ぶ（Authorization なし。limit は既定 4）。応答の配列をそのまま返す', async () => {
    const fetchMock = reply(200, [{ id: 8 }, { id: 9 }]);
    await expect(fetchRelatedRecruits(7)).resolves.toEqual([{ id: 8 }, { id: 9 }]);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toMatch(/\/api\/recruits\/7\/related\?limit=4$/);
    expect(init?.method).toBe('GET');
    expect((init?.headers as Record<string, string>).Authorization).toBeUndefined();
    expect(init?.cache).toBe('no-store');
  });

  it('limit を渡せる。空の配列も、そのまま返す', async () => {
    const fetchMock = reply(200, []);
    await expect(fetchRelatedRecruits(7, 12)).resolves.toEqual([]);
    expect(String(fetchMock.mock.calls[0]![0])).toMatch(/\/related\?limit=12$/);
  });

  it('404（存在しない・表示中でない求人）・接続できないときは ApiError（呼び出し側が空にする）', async () => {
    reply(404, { detail: '求人が見つかりません' });
    await expect(fetchRelatedRecruits(99)).rejects.toMatchObject({ status: 404 });
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('connect ECONNREFUSED 10.0.0.5:8000'));
    const error = await fetchRelatedRecruits(1).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(0);
    expect((error as ApiError).message).not.toContain('ECONNREFUSED');
  });
});

describe('fetchRecommendations', () => {
  it('JWT を Bearer で付けて GET する（limit は既定 6）', async () => {
    const fetchMock = reply(200, [{ id: 3 }]);
    await expect(fetchRecommendations('jwt-123')).resolves.toEqual([{ id: 3 }]);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toMatch(/\/api\/recommendations\?limit=6$/);
    expect(init?.method).toBe('GET');
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer jwt-123');
  });

  it('履歴が無い（[]）はそのまま返す。401 は ApiError', async () => {
    reply(200, []);
    await expect(fetchRecommendations('jwt', 3)).resolves.toEqual([]);
    reply(401, { detail: 'ログインしてください' });
    await expect(fetchRecommendations('expired')).rejects.toMatchObject({ status: 401 });
  });
});

describe('recordRecruitView', () => {
  it('JWT を Bearer で付けて、POST /api/recruits/ID/view を呼ぶ（本文なし）。204 で何も返さない', async () => {
    const fetchMock = reply(204);
    await expect(recordRecruitView('jwt-123', 7)).resolves.toBeUndefined();
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toMatch(/\/api\/recruits\/7\/view$/);
    expect(init?.method).toBe('POST');
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer jwt-123');
    expect(init?.body).toBeUndefined();
  });

  it.each([401, 404, 500])('%i は ApiError（例外の本文は固定の文）', async (status) => {
    reply(status, { detail: 'x' });
    await expect(recordRecruitView('jwt', 7)).rejects.toMatchObject({ status, message: `API がエラーを返しました（${status}）` });
  });
});
