import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { parseSelection } from '../lib/search';
import type { Facets, Master } from '../lib/types';
import { FilterForm } from './FilterForm';

const push = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));

const master: Master = {
  employments: [
    { code: 1, name: '常勤' },
    { code: 2, name: '短時間勤務' },
  ],
  areas: [
    { code: 3, name: '第一環' },
    { code: 4, name: '第二環' },
  ],
  stations: [{ code: 1, name: '鹿児島本線' }],
  occupations: [
    {
      category: '栽培',
      items: [
        { code: 1, name: '無重力蔓の育成士' },
        { code: 2, name: '人工夜の温室管理員' },
      ],
    },
    { category: '解説・案内', items: [{ code: 20, name: '案内所の係' }] },
  ],
};

const facets: Facets = {
  total: 11,
  employments: [
    { code: 1, count: 5 },
    { code: 2, count: 3 },
  ],
  areas: [{ code: 3, count: 2 }],
  stations: [{ code: 1, count: 2 }],
  occupations: [{ code: 1, count: 2 }],
};

beforeEach(() => push.mockReset());

/** チップ（<summary>）。名前は「ラベル 値」。 */
const chip = (label: string) => screen.getByText(label, { selector: '.facet-label' }).closest('summary') as HTMLElement;
const facetOf = (label: string) => chip(label).closest('details') as HTMLDetailsElement;

describe('FilterForm（上の横並びのチップ）', () => {
  it('4 つのチップを並べ、選んでいなければ「すべて」と出す', () => {
    render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
    for (const label of ['雇用形態', 'エリア', '最寄りの乗り場', '職種']) {
      expect(chip(label)).toHaveTextContent(`${label}すべて`);
      expect(facetOf(label)).toHaveAttribute('data-active', 'false');
    }
  });

  it('選んだ条件は、チップに出して強調する（1 つならその名前、2 つ以上なら「先頭の名前 ほか N」）', () => {
    render(<FilterForm master={master} facets={facets} selection={parseSelection({ employment: '2', area: ['3', '4'], occupation: '20' })} />);
    expect(chip('雇用形態')).toHaveTextContent('短時間勤務');
    expect(chip('エリア')).toHaveTextContent('第一環ほか1');
    expect(chip('職種')).toHaveTextContent('案内所の係');
    expect(chip('最寄りの乗り場')).toHaveTextContent('すべて');
    expect(facetOf('エリア')).toHaveAttribute('data-active', 'true');
    expect(facetOf('最寄りの乗り場')).toHaveAttribute('data-active', 'false');
  });

  it('選択肢ごとの件数を出す。件数が無いものは 0 と出す', () => {
    render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
    expect(screen.getByRole('checkbox', { name: '常勤', hidden: true }).closest('.option')).toHaveTextContent('5');
    expect(screen.getByRole('checkbox', { name: '第二環', hidden: true }).closest('.option')).toHaveTextContent('0');
  });

  it('チェックを入れると、その条件を足した URL へ移り、ページは 1 に戻す。チップの表示も変わる', async () => {
    render(<FilterForm master={master} facets={facets} selection={parseSelection({ area: '3', page: '2' })} />);
    await userEvent.click(chip('雇用形態'));
    await userEvent.click(screen.getByRole('checkbox', { name: '常勤' }));
    expect(push).toHaveBeenCalledWith('/?employment=1&area=3', { scroll: false });
    expect(screen.getByRole('checkbox', { name: '常勤' })).toBeChecked();
    expect(chip('雇用形態')).toHaveTextContent('常勤');
  });

  it('チェックを外すと、その条件だけを外した URL へ移る', async () => {
    render(<FilterForm master={master} facets={facets} selection={parseSelection({ area: ['3', '4'] })} />);
    await userEvent.click(chip('エリア'));
    await userEvent.click(screen.getByRole('checkbox', { name: '第一環' }));
    expect(push).toHaveBeenCalledWith('/?area=4', { scroll: false });
  });

  it('URL（選択）が外から変わったら、チェックとチップの表示を合わせ直す', () => {
    const { rerender } = render(<FilterForm master={master} facets={facets} selection={parseSelection({ area: '3' })} />);
    expect(screen.getByRole('checkbox', { name: '第一環', hidden: true })).toBeChecked();
    expect(chip('エリア')).toHaveTextContent('第一環');
    rerender(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
    expect(screen.getByRole('checkbox', { name: '第一環', hidden: true })).not.toBeChecked();
    expect(chip('エリア')).toHaveTextContent('すべて');
  });

  it('職種は区分ごとに折りたたむ。選んだ職種がある区分だけ最初から開く', () => {
    render(<FilterForm master={master} facets={facets} selection={parseSelection({ occupation: '20' })} />);
    const groups = document.querySelectorAll('.facet-panel details');
    expect(groups).toHaveLength(2);
    expect(groups[0]).not.toHaveAttribute('open');
    expect(groups[1]).toHaveAttribute('open');
    expect(screen.getByText('1 件選択中')).toBeInTheDocument();
  });

  it('JavaScript が無くても送れるよう、GET のフォームで name=種類・value=番号にしている', () => {
    render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
    const form = screen.getByRole('form', { name: '求人のしぼり込み' });
    expect(form).toHaveAttribute('method', 'get');
    expect(screen.getByRole('checkbox', { name: '常勤', hidden: true })).toHaveAttribute('name', 'employment');
    expect(screen.getByRole('checkbox', { name: '第一環', hidden: true })).toHaveAttribute('value', '3');
  });

  it('JavaScript が動いているあいだは、送信ボタンを隠す（無いときだけ、ボタンで送る）', () => {
    render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
    expect(screen.getByText('この条件でさがす', { selector: 'button' })).toHaveAttribute('hidden');
  });

  describe('一覧の開閉', () => {
    it('別のチップを開くと、前に開いていたチップは閉じる', async () => {
      render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
      await userEvent.click(chip('雇用形態'));
      await waitFor(() => expect(facetOf('雇用形態').open).toBe(true));
      await userEvent.click(chip('エリア'));
      await waitFor(() => expect(facetOf('エリア').open).toBe(true));
      await waitFor(() => expect(facetOf('雇用形態').open).toBe(false));
    });

    it('外を押すと閉じる。一覧の中を押しても閉じない', async () => {
      render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
      await userEvent.click(chip('雇用形態'));
      await waitFor(() => expect(facetOf('雇用形態').open).toBe(true));
      await userEvent.click(screen.getByRole('checkbox', { name: '短時間勤務' }));
      expect(facetOf('雇用形態').open).toBe(true);
      await userEvent.click(document.body);
      expect(facetOf('雇用形態').open).toBe(false);
    });

    it('フォーカスが一覧の外へ出たら閉じる。一覧の中でのフォーカスの移動では閉じない', async () => {
      render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
      await userEvent.click(chip('エリア'));
      await waitFor(() => expect(facetOf('エリア').open).toBe(true));
      const first = screen.getByRole('checkbox', { name: '第一環' });
      const second = screen.getByRole('checkbox', { name: '第二環' });
      fireEvent.focusOut(first, { relatedTarget: second });
      expect(facetOf('エリア').open).toBe(true);
      fireEvent.focusOut(second, { relatedTarget: document.body });
      expect(facetOf('エリア').open).toBe(false);
    });

    it('ウィンドウを離れただけ（移り先なし）では閉じない', async () => {
      render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
      await userEvent.click(chip('エリア'));
      await waitFor(() => expect(facetOf('エリア').open).toBe(true));
      fireEvent.focusOut(screen.getByRole('checkbox', { name: '第一環' }), { relatedTarget: null });
      expect(facetOf('エリア').open).toBe(true);
    });

    it('ほかの処理が先に受けた Esc（preventDefault 済み）では、閉じない', async () => {
      render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
      await userEvent.click(chip('エリア'));
      await waitFor(() => expect(facetOf('エリア').open).toBe(true));
      const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
      event.preventDefault();
      screen.getByRole('checkbox', { name: '第一環' }).dispatchEvent(event);
      expect(facetOf('エリア').open).toBe(true);
    });

    it('画面の幅が変わったら閉じる', async () => {
      render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
      await userEvent.click(chip('エリア'));
      await waitFor(() => expect(facetOf('エリア').open).toBe(true));
      fireEvent(window, new Event('resize'));
      expect(facetOf('エリア').open).toBe(false);
    });

    it('開いた一覧が画面の右へはみ出すときだけ、チップの右端にそろえる（data-align）', async () => {
      const rect = (right: number) => ({ right, left: 0, top: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;
      const spy = vi.spyOn(Element.prototype, 'getBoundingClientRect');
      render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
      Object.defineProperty(document.documentElement, 'clientWidth', { configurable: true, value: 1000 });
      spy.mockReturnValue(rect(1100));
      await userEvent.click(chip('エリア'));
      await waitFor(() => expect(facetOf('エリア')).toHaveAttribute('data-align', 'end'));
      // 収まる幅なら付けない（開き直したとき）
      await userEvent.click(chip('エリア'));
      await waitFor(() => expect(facetOf('エリア').open).toBe(false));
      spy.mockReturnValue(rect(500));
      await userEvent.click(chip('エリア'));
      await waitFor(() => expect(facetOf('エリア').open).toBe(true));
      expect(facetOf('エリア')).not.toHaveAttribute('data-align');
      delete (document.documentElement as unknown as Record<string, unknown>).clientWidth;
    });

    it('Esc で閉じて、フォーカスをチップへ戻す', async () => {
      render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
      await userEvent.click(chip('エリア'));
      await waitFor(() => expect(facetOf('エリア').open).toBe(true));
      await userEvent.click(screen.getByRole('checkbox', { name: '第一環' }));
      await userEvent.keyboard('{Escape}');
      expect(facetOf('エリア').open).toBe(false);
      expect(chip('エリア')).toHaveFocus();
    });
  });
});
