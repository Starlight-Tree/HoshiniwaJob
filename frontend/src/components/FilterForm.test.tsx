import { render, screen } from '@testing-library/react';
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

describe('FilterForm', () => {
  it('選択肢ごとの件数を出す。件数が無いものは 0 と出す', () => {
    render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
    expect(screen.getByRole('checkbox', { name: '常勤' }).closest('.option')).toHaveTextContent('5');
    expect(screen.getByRole('checkbox', { name: '第二環' }).closest('.option')).toHaveTextContent('0');
  });

  it('チェックを入れると、その条件を足した URL へ移り、ページは 1 に戻す', async () => {
    render(<FilterForm master={master} facets={facets} selection={parseSelection({ area: '3', page: '2' })} />);
    await userEvent.click(screen.getByRole('checkbox', { name: '常勤' }));
    expect(push).toHaveBeenCalledWith('/?employment=1&area=3', { scroll: false });
    expect(screen.getByRole('checkbox', { name: '常勤' })).toBeChecked();
  });

  it('チェックを外すと、その条件だけを外した URL へ移る', async () => {
    render(<FilterForm master={master} facets={facets} selection={parseSelection({ area: ['3', '4'] })} />);
    await userEvent.click(screen.getByRole('checkbox', { name: '第一環' }));
    expect(push).toHaveBeenCalledWith('/?area=4', { scroll: false });
  });

  it('URL（選択）が外から変わったら、チェックの状態を合わせ直す', () => {
    const { rerender } = render(<FilterForm master={master} facets={facets} selection={parseSelection({ area: '3' })} />);
    expect(screen.getByRole('checkbox', { name: '第一環' })).toBeChecked();
    rerender(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
    expect(screen.getByRole('checkbox', { name: '第一環' })).not.toBeChecked();
  });

  it('職種は区分ごとに折りたたむ。選んだ職種がある区分だけ最初から開く', () => {
    render(<FilterForm master={master} facets={facets} selection={parseSelection({ occupation: '20' })} />);
    const groups = document.querySelectorAll('details');
    expect(groups).toHaveLength(2);
    expect(groups[0]).not.toHaveAttribute('open');
    expect(groups[1]).toHaveAttribute('open');
    expect(screen.getByText('1 件選択中')).toBeInTheDocument();
  });

  it('JavaScript が無くても送れるよう、GET のフォームで name=種類・value=番号にしている', () => {
    render(<FilterForm master={master} facets={facets} selection={parseSelection({})} />);
    const form = screen.getByRole('form', { name: '求人のしぼり込み' });
    expect(form).toHaveAttribute('method', 'get');
    expect(screen.getByRole('checkbox', { name: '常勤' })).toHaveAttribute('name', 'employment');
    expect(screen.getByRole('checkbox', { name: '第一環' })).toHaveAttribute('value', '3');
  });
});
