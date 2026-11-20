import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from './api';
import { loadRecruit } from './load-recruit';

const api = vi.hoisted(() => ({ fetchRecruit: vi.fn() }));
vi.mock('./api', async (importOriginal) => ({ ...(await importOriginal<typeof import('./api')>()), fetchRecruit: api.fetchRecruit }));
// 本物の notFound() は、404 の描画へ切り替える例外を投げる。ここでは、それと分かる例外にする
vi.mock('next/navigation', () => ({
  notFound: () => {
    throw new Error('NEXT_NOT_FOUND');
  },
}));

// 波かっこで囲む（beforeEach は、関数を返すと、それを各テストのあとの後始末として呼ぶ。モックを返すと、モックが呼ばれてしまう）
beforeEach(() => {
  api.fetchRecruit.mockReset();
});

describe('loadRecruit', () => {
  it('求人を返す（ID は文字列で受け、数値で API へ）', async () => {
    api.fetchRecruit.mockResolvedValue({ id: 7 });
    await expect(loadRecruit('7')).resolves.toEqual({ id: 7 });
    expect(api.fetchRecruit).toHaveBeenCalledWith(7);
  });

  it.each(['0', '-1', '1.5', 'abc', ''])('ID が正の整数でない（%j）と、API を呼ばず notFound', async (id) => {
    await expect(loadRecruit(id)).rejects.toThrow('NEXT_NOT_FOUND');
    expect(api.fetchRecruit).not.toHaveBeenCalled();
  });

  it('API が 404 なら notFound', async () => {
    api.fetchRecruit.mockImplementation(async () => {
      throw new ApiError(404, 'API がエラーを返しました（404）');
    });
    await expect(loadRecruit('99')).rejects.toThrow('NEXT_NOT_FOUND');
  });

  it('接続できない・5xx は null（呼び出し側が固定の文を出す。例外の文面は出さない）', async () => {
    api.fetchRecruit.mockImplementationOnce(async () => {
      throw new ApiError(0, 'API に接続できません');
    });
    await expect(loadRecruit('1')).resolves.toBeNull();
    api.fetchRecruit.mockImplementationOnce(async () => {
      throw new ApiError(500, 'API がエラーを返しました（500）');
    });
    await expect(loadRecruit('2')).resolves.toBeNull();
  });
});
