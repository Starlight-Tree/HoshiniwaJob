import { userToken } from '../lib/session';
import { ViewBeacon } from './ViewBeacon';

/**
 * 求人の詳細（ページ・パネル）の中に置く、閲覧の記録の入口（Server Component。何も描かない）。
 * 求職者がログインしているとき（API へ渡せる JWT が取れるとき）だけ、記録を送る部品（ViewBeacon）を出す。未ログインでは何も出さず、API も呼ばない。
 * 同じ描画の中では、userToken は 1 回しか取らない（lib/session.ts の cache）。
 */
export async function RecruitViewRecorder({ recruitId }: { recruitId: number }) {
  if ((await userToken()) === null) return null;
  return <ViewBeacon recruitId={recruitId} />;
}
