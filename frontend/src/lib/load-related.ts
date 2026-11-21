import { fetchRecommendations, fetchRelatedRecruits } from './api';
import { userToken } from './session';
import type { RecruitSummary } from './types';

// 出す件数。API の上限は 12（docs/recommendation.md）。画面の都合で、関連は 4、おすすめは 6
export const RELATED_LIMIT = 4;
export const RECOMMENDATION_LIMIT = 6;

// 関連・おすすめは「付いていれば出る」もの。取れなかったら、節ごと出さないだけで、画面（詳細・一覧）は壊さない。
// 例外の文面は画面に出さない・ログにも残さない（接続できない・404・5xx・形が違う、のどれも [] にする）
const listOrEmpty = (value: unknown): RecruitSummary[] => (Array.isArray(value) ? (value as RecruitSummary[]) : []);

/**
 * 求人 id の「関連する求人」を API から読む（サーバー側だけ。公開 API なので、ログインは要らない）。
 * id は文字列（URL のまま）で受ける。正の整数でなければ、API を呼ばず []。取れなかったときも []（この関数は例外を投げない）。
 */
export async function loadRelated(id: string): Promise<RecruitSummary[]> {
  const n = Number(id);
  if (!Number.isInteger(n) || n < 1) return [];
  try {
    return listOrEmpty(await fetchRelatedRecruits(n, RELATED_LIMIT));
  } catch {
    return [];
  }
}

/**
 * ログイン中の求職者の「あなたへのおすすめ」を API から読む（サーバー側だけ）。
 * ログインしていなければ、API を呼ばず []（401 を出さない）。履歴が無いときも API が [] を返す。取れなかったときも []（この関数は例外を投げない）。
 */
export async function loadRecommendations(): Promise<RecruitSummary[]> {
  const token = await userToken();
  if (!token) return [];
  try {
    return listOrEmpty(await fetchRecommendations(token, RECOMMENDATION_LIMIT));
  } catch {
    return [];
  }
}
