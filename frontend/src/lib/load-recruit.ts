import { notFound } from 'next/navigation';
import { cache } from 'react';
import { ApiError, fetchRecruit } from './api';

/**
 * 求人 1 件を API から読む（サーバー側だけ）。詳細ページ（/recruits/ID）と、一覧に重ねる詳細パネル（@panel の (.)recruits/[id]）の両方が使う。
 * generateMetadata と本体で同じ求人を 2 回読まないよう、同じ描画の中では結果を使い回す（React の cache）。
 * ID が正の整数でないとき・API が 404 を返したときは notFound()。それ以外の失敗（接続できない・5xx）は null を返し、呼び出し側が固定の文を出す（例外の文面は画面に出さない）。
 */
export const loadRecruit = cache(async (id: string) => {
  const n = Number(id);
  if (!Number.isInteger(n) || n < 1) notFound();
  try {
    return await fetchRecruit(n);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return null;
  }
});
