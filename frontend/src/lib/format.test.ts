import { describe, expect, it } from 'vitest';
import { payOf, payRange, salaryLabel, shownRange } from './format';

describe('payRange', () => {
  it('1 万以上は万で、それ未満はそのままノクトで出す', () => {
    expect(payRange(180000, 240000)).toBe('18〜24万ノクト');
    expect(payRange(185000, 230000)).toBe('18.5〜23万ノクト');
    expect(payRange(1100, 1300)).toBe('1,100〜1,300ノクト');
  });

  it('最低と最高が同じなら 1 つだけ。片方だけでもそれを出す', () => {
    expect(payRange(200000, 200000)).toBe('20万ノクト');
    expect(payRange(null, 1200)).toBe('1,200ノクト');
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
    expect(payOf({ salary: 4, pay_min: 1000, pay_max: 1200 })).toEqual({ label: '時給', value: '1,000〜1,200ノクト' });
  });
});

describe('shownRange', () => {
  it('件数の範囲。0 件は空', () => {
    expect(shownRange(1, 10, 11)).toBe('1〜10 件を表示');
    expect(shownRange(2, 10, 11)).toBe('11〜11 件を表示');
    expect(shownRange(1, 10, 0)).toBe('');
  });
});
