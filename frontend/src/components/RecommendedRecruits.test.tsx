import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { RecruitSummary } from '../lib/types';
import { RecommendedRecruits } from './RecommendedRecruits';

const nav = vi.hoisted(() => ({ pathname: '/' }));
vi.mock('next/navigation', () => ({ usePathname: () => nav.pathname }));

function job(id: number): RecruitSummary {
  return {
    id,
    corporate: '星庭ワークス',
    category: `職種 ${id}`,
    salary: 2,
    pay_min: 180000,
    pay_max: 240000,
    comment1: null,
    note1: null,
    formfile: null,
    areas: ['北の丘'],
    stations: [],
    occupations: [],
    employments: ['正社員'],
    hero_image: null,
  };
}

beforeEach(() => {
  nav.pathname = '/';
});

describe('RecommendedRecruits（あなたへのおすすめ）', () => {
  it('履歴が無い（[]）なら、帯ごと出さない', () => {
    const { container } = render(<RecommendedRecruits jobs={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('見出し h2「あなたへのおすすめ」の帯に、一覧と同じカード（SelectableCard）を、渡された順に並べる。カードの題名は h3', () => {
    const { container } = render(<RecommendedRecruits jobs={[job(4), job(2), job(9)]} />);
    const band = screen.getByRole('region', { name: 'あなたへのおすすめ' });
    expect(within(band).getByRole('heading', { level: 2, name: 'あなたへのおすすめ' })).toBeInTheDocument();
    expect(container.querySelectorAll('.recs-list .card-slot article.card')).toHaveLength(3);
    expect(within(band).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['職種 4', '職種 2', '職種 9']);
    expect(within(band).getAllByRole('heading', { level: 2 })).toHaveLength(1);
    expect(within(band).getByRole('link', { name: '職種 4' })).toHaveAttribute('href', '/recruits/4');
  });

  it('その求人の詳細パネルが開いている（URL が /recruits/ID）カードは、選択状態（aria-current）になる', () => {
    nav.pathname = '/recruits/2';
    const { container } = render(<RecommendedRecruits jobs={[job(4), job(2)]} />);
    const slots = [...container.querySelectorAll('.card-slot')];
    expect(slots.map((s) => s.getAttribute('aria-current'))).toEqual([null, 'true']);
  });

  it('一覧に同じ求人のカードがありうるので、フォーカスを戻す目印（data-recruit-id）は付けない', () => {
    const { container } = render(<RecommendedRecruits jobs={[job(4)]} />);
    expect(container.querySelector('[data-recruit-id]')).toBeNull();
  });

  it('文は、事実のとおり（「これまでに見た求人」をもとにする。「最近」「機械学習・AI」とは書かない）。理由を添える', () => {
    render(<RecommendedRecruits jobs={[job(4)]} />);
    const note = screen.getByText(/選んでいます/);
    expect(note.textContent).toContain('これまでに見た求人をもとに');
    expect(note.textContent).toContain('雇用形態・エリア・職種の近い求人');
    expect(note.textContent).toContain('同じ求人を見た人がほかに見ている求人');
    expect(document.body.textContent).not.toMatch(/最近|機械学習|AI/);
  });
});
