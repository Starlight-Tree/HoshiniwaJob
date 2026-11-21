'use server';

import { recordRecruitView } from '../lib/api';
import { userToken } from '../lib/session';

/**
 * 求人の閲覧を記録する（求職者がログインしているときだけ。ViewBeacon が、詳細を開いたあとにブラウザーから 1 回呼ぶ）。
 * ブラウザーは API を直接呼ばない。ここ（サーバー）が、Better Auth の Cookie から取った JWT を付けて API を呼ぶ。
 * 記録は付随の処理なので、何も返さず、失敗（未ログイン・期限切れ・404・接続できない）も画面には出さない。
 * 未ログインのときは API を呼ばない（401 を出さない）。同じ求人を 30 分以内に何度送っても、API が 1 件にまとめる（docs/recommendation.md）。
 */
export async function recordViewAction(recruitId: number): Promise<void> {
  // サーバーアクションは、ブラウザーから任意の値で呼べる。正の整数以外は、API へ回さない
  if (!Number.isInteger(recruitId) || recruitId < 1) return;
  const token = await userToken();
  if (!token) return;
  try {
    await recordRecruitView(token, recruitId);
  } catch {
    // 付随の処理。失敗しても何も変えない（例外の文字列は出さない・残さない）
  }
}
