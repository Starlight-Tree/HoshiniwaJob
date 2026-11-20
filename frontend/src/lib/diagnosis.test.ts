import { describe, expect, it } from 'vitest';
import { isSubmitted, nameOf, parseAnswers, rank, reasonOf, selectionOf, wantedOf } from './diagnosis';
import type { Master, RecruitSummary } from './types';

const MASTER: Master = {
  employments: [
    { code: 1, name: '常勤' },
    { code: 2, name: '短時間勤務' },
  ],
  areas: [
    { code: 10, name: '第一環' },
    { code: 11, name: '第二環' },
  ],
  stations: [],
  occupations: [{ category: '栽培', items: [{ code: 100, name: '蔓の育成' }, { code: 101, name: '土壌の分析' }] }],
};

function job(id: number, o: Partial<RecruitSummary> = {}): RecruitSummary {
  return {
    id,
    corporate: null,
    category: null,
    salary: null,
    pay_min: null,
    pay_max: null,
    comment1: null,
    note1: null,
    formfile: null,
    areas: [],
    stations: [],
    occupations: [],
    employments: [],
    hero_image: null,
    ...o,
  };
}

describe('parseAnswers / isSubmitted', () => {
  it('数字を答えにし、空（こだわらない）・数字でない値・0 以下は null', () => {
    expect(parseAnswers({ employment: '1', area: '', occupation: 'x' })).toEqual({ employment: 1, area: null, occupation: null });
    expect(parseAnswers({ employment: '0', area: '-3' })).toEqual({ employment: null, area: null, occupation: null });
  });

  it('同じ名前が複数あっても、最初の有効な値を使う', () => {
    expect(parseAnswers({ area: ['', '11', '10'] }).area).toBe(11);
  });

  it('質問の名前が 1 つでもクエリにあれば、送られた後。無ければ初めて開いた状態', () => {
    expect(isSubmitted({})).toBe(false);
    expect(isSubmitted({ page: '2' })).toBe(false);
    expect(isSubmitted({ employment: '' })).toBe(true);
  });
});

describe('wantedOf / nameOf', () => {
  it('こだわらない・マスタに無い番号は、使う条件から除く', () => {
    expect(wantedOf({ employment: 1, area: null, occupation: 999 }, MASTER)).toEqual([{ kind: 'employment', code: 1, name: '常勤' }]);
  });

  it('職種は区分をまたいで名前を引く', () => {
    expect(nameOf(MASTER, 'occupation', 101)).toBe('土壌の分析');
  });
});

describe('rank', () => {
  const jobs = [
    job(1, { employments: ['常勤'], areas: ['第二環'], occupations: ['土壌の分析'] }),
    job(2, { employments: ['常勤'], areas: ['第一環'], occupations: ['蔓の育成'] }),
    job(3, { employments: ['短時間勤務'], areas: ['第一環'], occupations: ['蔓の育成'] }),
    job(4, { employments: ['短時間勤務'], areas: ['第二環'], occupations: ['土壌の分析'] }),
  ];

  it('合った条件の数が多い順に並べる（3 つ → 2 つ → 1 つ。1 つも合わない 4 番は出ない）', () => {
    const out = rank(jobs, { employment: 1, area: 10, occupation: 100 }, MASTER);
    expect(out.map((m) => [m.job.id, m.hits.length])).toEqual([
      [2, 3],
      [3, 2],
      [1, 1],
    ]);
  });

  it('合った数が同じなら、番号の順', () => {
    const out = rank([job(9, { areas: ['第一環'] }), job(5, { areas: ['第一環'] })], { employment: null, area: 10, occupation: null }, MASTER);
    expect(out.map((m) => m.job.id)).toEqual([5, 9]);
  });

  it('1 つも合わない求人は出さない', () => {
    const out = rank(jobs, { employment: 1, area: null, occupation: null }, MASTER);
    expect(out.map((m) => m.job.id)).toEqual([1, 2]);
  });

  it('条件が 1 つも無いとき（すべてこだわらない）は空', () => {
    expect(rank(jobs, { employment: null, area: null, occupation: null }, MASTER)).toEqual([]);
  });

  it('どの条件が合ったかを持つ', () => {
    const top = rank(jobs, { employment: 1, area: 10, occupation: null }, MASTER)[0];
    expect(top?.job.id).toBe(2);
    expect(top?.hits).toEqual(['employment', 'area']);
    expect(top?.total).toBe(2);
  });
});

describe('selectionOf / reasonOf', () => {
  it('求人検索の条件にする（駅は使わず、ページは 1）', () => {
    expect(selectionOf({ employment: 1, area: null, occupation: 100 })).toEqual({ employment: [1], area: [], station: [], occupation: [100], q: '', page: 1 });
  });

  it('一致の説明: 条件 1 つ／すべて／一部', () => {
    const j = job(1);
    expect(reasonOf({ job: j, hits: ['area'], total: 1 })).toBe('一致した条件：エリア');
    expect(reasonOf({ job: j, hits: ['employment', 'area'], total: 2 })).toBe('すべての条件に一致（働き方・エリア）');
    expect(reasonOf({ job: j, hits: ['occupation'], total: 3 })).toBe('3 つ中 1 つ一致（職種）');
  });
});
