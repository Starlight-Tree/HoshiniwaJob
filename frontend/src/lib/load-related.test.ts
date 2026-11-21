import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from './api';
import { loadRecommendations, loadRelated, RECOMMENDATION_LIMIT, RELATED_LIMIT } from './load-related';

const api = vi.hoisted(() => ({ fetchRelatedRecruits: vi.fn(), fetchRecommendations: vi.fn() }));
vi.mock('./api', async (importOriginal) => ({ ...(await importOriginal<typeof import('./api')>()), ...api }));
const session = vi.hoisted(() => ({ token: null as string | null }));
vi.mock('./session', () => ({ userToken: async () => session.token }));

// 波かっこで囲む（beforeEach は、関数を返すと、それを後始末として呼ぶため）
beforeEach(() => {
  api.fetchRelatedRecruits.mockReset();
  api.fetchRecommendations.mockReset();
  session.token = null;
});

describe('loadRelated', () => {
  it('ID は文字列で受け、数値と件数（4）で API を呼んで、配列を返す', async () => {
    api.fetchRelatedRecruits.mockResolvedValue([{ id: 8 }]);
    await expect(loadRelated('7')).resolves.toEqual([{ id: 8 }]);
    expect(api.fetchRelatedRecruits).toHaveBeenCalledWith(7, RELATED_LIMIT);
    expect(RELATED_LIMIT).toBe(4);
  });

  it.each(['0', '-1', '1.5', 'abc', ''])('ID が正の整数でない（%j）と、API を呼ばず []', async (id) => {
    await expect(loadRelated(id)).resolves.toEqual([]);
    expect(api.fetchRelatedRecruits).not.toHaveBeenCalled();
  });

  it('取れなかったとき（404・5xx・接続できない）は、例外を投げず []（画面は節ごと出さないだけ）', async () => {
    for (const status of [404, 500, 0]) {
      api.fetchRelatedRecruits.mockImplementationOnce(async () => {
        throw new ApiError(status, 'x');
      });
      await expect(loadRelated('7')).resolves.toEqual([]);
    }
  });

  it('応答が配列でなければ []', async () => {
    api.fetchRelatedRecruits.mockResolvedValue({ detail: 'x' });
    await expect(loadRelated('7')).resolves.toEqual([]);
  });
});

describe('loadRecommendations', () => {
  it('ログイン中は、JWT と件数（6）で API を呼んで、配列を返す', async () => {
    session.token = 'jwt-123';
    api.fetchRecommendations.mockResolvedValue([{ id: 3 }, { id: 4 }]);
    await expect(loadRecommendations()).resolves.toEqual([{ id: 3 }, { id: 4 }]);
    expect(api.fetchRecommendations).toHaveBeenCalledWith('jwt-123', RECOMMENDATION_LIMIT);
    expect(RECOMMENDATION_LIMIT).toBe(6);
  });

  it('ログインしていない（JWT が取れない）と、API を呼ばず []（401 を出さない）', async () => {
    await expect(loadRecommendations()).resolves.toEqual([]);
    expect(api.fetchRecommendations).not.toHaveBeenCalled();
  });

  it('履歴が無い（[]）・取れなかった（401・5xx・接続できない）ときは []。例外を投げない', async () => {
    session.token = 'jwt';
    api.fetchRecommendations.mockResolvedValueOnce([]);
    await expect(loadRecommendations()).resolves.toEqual([]);
    for (const status of [401, 500, 0]) {
      api.fetchRecommendations.mockImplementationOnce(async () => {
        throw new ApiError(status, 'x');
      });
      await expect(loadRecommendations()).resolves.toEqual([]);
    }
  });
});
