import { describe, expect, it } from 'vitest';
import { chipsFor, hasConditions, hrefFor, parseSelection, toQuery } from './search';
import type { Master } from './types';

const master: Master = {
  areas: [{ code: 3, name: '第一環' }],
  stations: [{ code: 1, name: '鹿児島本線' }],
  occupations: [{ category: '栽培', items: [{ code: 1, name: '無重力蔓の育成士' }] }],
  employments: [{ code: 1, name: '常勤' }],
};

describe('parseSelection', () => {
  it('数字でない値・0・重複を捨て、小さい順にそろえる', () => {
    const sel = parseSelection({ area: ['4', '3', 'x', '3', '0', '-2'], employment: '1', page: '3' });
    expect(sel.area).toEqual([3, 4]);
    expect(sel.employment).toEqual([1]);
    expect(sel.page).toBe(3);
  });

  it('page が壊れていれば 1 にする', () => {
    expect(parseSelection({ page: 'abc' }).page).toBe(1);
    expect(parseSelection({ page: '0' }).page).toBe(1);
    expect(parseSelection({ page: '1.5' }).page).toBe(1);
    expect(parseSelection({}).page).toBe(1);
  });
});

describe('toQuery / hrefFor', () => {
  it('条件が無ければ / だけ。page=1 は付けない', () => {
    expect(hrefFor(parseSelection({}))).toBe('/');
    expect(toQuery(parseSelection({ page: '1' }))).toBe('');
  });

  it('同じ種類は繰り返しの形で書く', () => {
    expect(toQuery(parseSelection({ area: ['3', '4'], employment: '1', page: '2' }))).toBe(
      'employment=1&area=3&area=4&page=2',
    );
  });

  it('hasConditions はページだけでは true にならない', () => {
    expect(hasConditions(parseSelection({ page: '4' }))).toBe(false);
    expect(hasConditions(parseSelection({ station: '1' }))).toBe(true);
  });
});

describe('chipsFor', () => {
  it('選んだ条件ごとに、その 1 つだけを外したリンクを作り、ページは 1 に戻す', () => {
    const sel = parseSelection({ area: '3', employment: '1', page: '2' });
    const chips = chipsFor(sel, master);
    expect(chips.map((c) => c.label)).toEqual(['常勤', '第一環']);
    expect(chips[0]?.removeHref).toBe('/?area=3');
    expect(chips[1]?.removeHref).toBe('/?employment=1');
  });

  it('マスタに無い番号はチップに出さない', () => {
    expect(chipsFor(parseSelection({ area: '99' }), master)).toEqual([]);
  });

  it('職種は区分の中から名前を引く', () => {
    expect(chipsFor(parseSelection({ occupation: '1' }), master).map((c) => c.label)).toEqual(['無重力蔓の育成士']);
  });
});
