import type { RecruitSummary } from './types';

// 給与の通貨は架空の「ルミ」（実在の通貨にしない）
const CURRENCY = 'ルミ';

const SALARY_LABELS: Record<number, string> = { 1: '年俸', 2: '月給', 3: '日給', 4: '時給' };

export function salaryLabel(salary: number | null): string {
  return (salary !== null && SALARY_LABELS[salary]) || '給与';
}

function yen(n: number): string {
  return n.toLocaleString('ja-JP');
}

/** 給与の範囲を、金額（amount）と単位（unit）に分けて返す。金額は全桁の数字（3 桁ごとの区切り）。値が無ければ「応相談」で、単位は空文字。画面では単位を小さく・薄くするために分けている。 */
export function payAmount(min: number | null, max: number | null): { amount: string; unit: string } {
  const lo = min ?? max;
  const hi = max ?? min;
  if (lo === null || hi === null || (lo === 0 && hi === 0)) return { amount: '応相談', unit: '' };
  return { amount: lo === hi ? yen(lo) : `${yen(lo)}〜${yen(hi)}`, unit: CURRENCY };
}

/** 給与の範囲を、金額と単位をつないだ 1 つの文字列で出す（例: 180,000〜240,000ルミ）。海外の求人サイトと同じ書き方（月給も時給も同じ形で、見比べやすい）。 */
export function payRange(min: number | null, max: number | null): string {
  const { amount, unit } = payAmount(min, max);
  return `${amount}${unit}`;
}

export function payOf(job: Pick<RecruitSummary, 'salary' | 'pay_min' | 'pay_max'>): { label: string; value: string; amount: string; unit: string } {
  return { label: salaryLabel(job.salary), value: payRange(job.pay_min, job.pay_max), ...payAmount(job.pay_min, job.pay_max) };
}

/** 一覧に出す件数の範囲（例: 1〜6 件を表示）。0 件のときは空。 */
export function shownRange(page: number, perPage: number, total: number): string {
  if (total === 0) return '';
  const from = (page - 1) * perPage + 1;
  const to = Math.min(total, page * perPage);
  return `${from}〜${to} 件を表示`;
}
