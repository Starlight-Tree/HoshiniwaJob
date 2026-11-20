import { describe, expect, it } from 'vitest';
import { payAmount, payOf, payRange, salaryLabel, shownRange } from './format';

describe('payAmount', () => {
  it('金額（3 桁ごとの区切り）と単位に分ける', () => {
    expect(payAmount(180000, 240000)).toEqual({ amount: '180,000〜240,000', unit: 'ルミ' });
    expect(payAmount(1100, 1300)).toEqual({ amount: '1,100〜1,300', unit: 'ルミ' });
  });

  it('最低と最高が同じなら 1 つだけ。片方だけでもそれを出す', () => {
    expect(payAmount(200000, 200000)).toEqual({ amount: '200,000', unit: 'ルミ' });
    expect(payAmount(null, 1200)).toEqual({ amount: '1,200', unit: 'ルミ' });
    expect(payAmount(1200, null)).toEqual({ amount: '1,200', unit: 'ルミ' });
  });

  it('値が無い・0 は応相談で、単位は空文字', () => {
    expect(payAmount(null, null)).toEqual({ amount: '応相談', unit: '' });
    expect(payAmount(0, 0)).toEqual({ amount: '応相談', unit: '' });
  });

  it('金額と単位をつなぐと payRange と同じ', () => {
    for (const [min, max] of [[180000, 240000], [200000, 200000], [null, 1200], [null, null], [0, 0]] as const) {
      const { amount, unit } = payAmount(min, max);
      expect(`${amount}${unit}`).toBe(payRange(min, max));
    }
  });
});

describe('payRange', () => {
  it('月給も時給も、全桁の数字（3 桁ごとの区切り）で出す', () => {
    expect(payRange(180000, 240000)).toBe('180,000〜240,000ルミ');
    expect(payRange(185000, 230000)).toBe('185,000〜230,000ルミ');
    expect(payRange(1100, 1300)).toBe('1,100〜1,300ルミ');
  });

  it('最低と最高が同じなら 1 つだけ。片方だけでもそれを出す', () => {
    expect(payRange(200000, 200000)).toBe('200,000ルミ');
    expect(payRange(null, 1200)).toBe('1,200ルミ');
  });

  it('値が無い・0 は応相談', () => {
    expect(payRange(null, null)).toBe('応相談');
    expect(payRange(0, 0)).toBe('応相談');
  });
});

describe('salaryLabel / payOf', () => {
  it('給与の種類（1 年俸 / 2 月給 / 3 日給 / 4 時給）', () => {
    expect(salaryLabel(2)).toBe('月給');
    expect(salaryLabel(4)).toBe('時給');
    expect(salaryLabel(null)).toBe('給与');
    expect(salaryLabel(9)).toBe('給与');
    expect(payOf({ salary: 4, pay_min: 1000, pay_max: 1200 })).toEqual({ label: '時給', value: '1,000〜1,200ルミ', amount: '1,000〜1,200', unit: 'ルミ' });
  });

  it('応相談は、value が「応相談」、unit が空文字（詳細ページは value だけ使う）', () => {
    expect(payOf({ salary: 2, pay_min: null, pay_max: null })).toEqual({ label: '月給', value: '応相談', amount: '応相談', unit: '' });
  });
});

describe('shownRange', () => {
  it('件数の範囲。0 件は空', () => {
    expect(shownRange(1, 10, 11)).toBe('1〜10 件を表示');
    expect(shownRange(2, 10, 11)).toBe('11〜11 件を表示');
    expect(shownRange(1, 10, 0)).toBe('');
  });
});
