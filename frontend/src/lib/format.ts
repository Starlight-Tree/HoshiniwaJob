import type { RecruitSummary } from './types';

// 給与の通貨は架空の「ノクト」（実在の通貨にしない）
const CURRENCY = 'ノクト';

const SALARY_LABELS: Record<number, string> = { 1: '年俸', 2: '月給', 3: '日給', 4: '時給' };

export function salaryLabel(salary: number | null): string {
  return (salary !== null && SALARY_LABELS[salary]) || '給与';
}

function yen(n: number): string {
  return n.toLocaleString('ja-JP');
}

// 1 万以上は「万」にし（18万ノクト、18.5万ノクト）、それ未満はそのまま（1,100ノクト）。
function man(n: number): string {
  return String(Math.round(n / 1000) / 10);
}

/** 給与の範囲を、一覧で見比べやすい短い文字にする。値が無ければ「応相談」。 */
export function payRange(min: number | null, max: number | null): string {
  const lo = min ?? max;
  const hi = max ?? min;
  if (lo === null || hi === null || (lo === 0 && hi === 0)) return '応相談';
  if (lo >= 10000) return lo === hi ? `${man(lo)}万${CURRENCY}` : `${man(lo)}〜${man(hi)}万${CURRENCY}`;
  return lo === hi ? `${yen(lo)}${CURRENCY}` : `${yen(lo)}〜${yen(hi)}${CURRENCY}`;
}

export function payOf(job: Pick<RecruitSummary, 'salary' | 'pay_min' | 'pay_max'>): { label: string; value: string } {
  return { label: salaryLabel(job.salary), value: payRange(job.pay_min, job.pay_max) };
}

/** 一覧に出す件数の範囲（例: 1〜6 件を表示）。0 件のときは空。 */
export function shownRange(page: number, perPage: number, total: number): string {
  if (total === 0) return '';
  const from = (page - 1) * perPage + 1;
  const to = Math.min(total, page * perPage);
  return `${from}〜${to} 件を表示`;
}
