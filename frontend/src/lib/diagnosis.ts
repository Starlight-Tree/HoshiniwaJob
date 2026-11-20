import type { Selection } from './search';
import type { Master, RecruitSummary } from './types';

// 「3 つの質問で診断」。機械学習は使わない。答えと求人の条件がいくつ合うかを数えて、多い順に並べるだけ（理由を説明できる）。
// 質問は、求人の絞り込み（lib/search.ts）と同じ条件の種類のうち、利用者が答えやすい 3 つ。

export const QUESTION_KINDS = ['employment', 'area', 'occupation'] as const;
export type QuestionKind = (typeof QUESTION_KINDS)[number];

/** 各質問の答え（条件の番号）。「こだわらない」は null。 */
export type Answers = Record<QuestionKind, number | null>;

export const QUESTION_LABEL: Record<QuestionKind, string> = {
  employment: '働き方',
  area: 'エリア',
  occupation: '職種',
};

type RawParams = Record<string, string | string[] | undefined>;

function firstCode(value: string | string[] | undefined): number | null {
  const list = Array.isArray(value) ? value : value === undefined ? [] : [value];
  for (const v of list) {
    const n = Number(v);
    if (v !== '' && Number.isInteger(n) && n > 0) return n;
  }
  return null;
}

/** URL のクエリを、答えにする。数字でない値・空（こだわらない）は null。 */
export function parseAnswers(params: RawParams): Answers {
  return {
    employment: firstCode(params.employment),
    area: firstCode(params.area),
    occupation: firstCode(params.occupation),
  };
}

/** フォームが送られた後か（1 つでも質問の名前がクエリにあるか）。初めて開いたときは、結果を出さない。 */
export function isSubmitted(params: RawParams): boolean {
  return QUESTION_KINDS.some((kind) => params[kind] !== undefined);
}

/** 条件の番号の名前。マスタに無い（削除済みの）番号は undefined。 */
export function nameOf(master: Master, kind: QuestionKind, code: number): string | undefined {
  if (kind === 'employment') return master.employments.find((c) => c.code === code)?.name;
  if (kind === 'area') return master.areas.find((c) => c.code === code)?.name;
  return master.occupations.flatMap((g) => g.items).find((c) => c.code === code)?.name;
}

export type Wanted = { kind: QuestionKind; code: number; name: string };

/** 答えのうち、実際に使う条件（「こだわらない」とマスタに無い番号は除く）。 */
export function wantedOf(answers: Answers, master: Master): Wanted[] {
  return QUESTION_KINDS.flatMap((kind) => {
    const code = answers[kind];
    const name = code === null ? undefined : nameOf(master, kind, code);
    return code !== null && name !== undefined ? [{ kind, code, name }] : [];
  });
}

const FIELD = { employment: 'employments', area: 'areas', occupation: 'occupations' } as const;

export type Match = { job: RecruitSummary; hits: QuestionKind[]; total: number };

/**
 * 求人を、合った条件の数が多い順（同じなら番号の順）に並べる。1 つも合わない求人は出さない。
 * 求人は名前で持っている（RecruitSummary）ので、マスタの名前で照らす。
 */
export function rank(jobs: RecruitSummary[], answers: Answers, master: Master): Match[] {
  const wanted = wantedOf(answers, master);
  if (wanted.length === 0) return [];
  return jobs
    .map((job) => ({ job, hits: wanted.filter((w) => job[FIELD[w.kind]].includes(w.name)).map((w) => w.kind), total: wanted.length }))
    .filter((m) => m.hits.length > 0)
    .sort((a, b) => b.hits.length - a.hits.length || a.job.id - b.job.id);
}

/** 求人検索（/）で同じ条件を開くための選び方。 */
export function selectionOf(answers: Answers): Selection {
  return {
    employment: answers.employment === null ? [] : [answers.employment],
    area: answers.area === null ? [] : [answers.area],
    station: [],
    occupation: answers.occupation === null ? [] : [answers.occupation],
    page: 1,
  };
}

/** 「3 つ中 2 つ一致（働き方・職種）」のような、一致の説明。 */
export function reasonOf(match: Match): string {
  const names = match.hits.map((kind) => QUESTION_LABEL[kind]).join('・');
  if (match.total === 1) return `一致した条件：${names}`;
  if (match.hits.length === match.total) return `すべての条件に一致（${names}）`;
  return `${match.total} つ中 ${match.hits.length} つ一致（${names}）`;
}
