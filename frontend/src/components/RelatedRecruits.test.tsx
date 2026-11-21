import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { RecruitSummary } from '../lib/types';
import { RelatedRecruits } from './RelatedRecruits';

function job(id: number, overrides: Partial<RecruitSummary> = {}): RecruitSummary {
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
    ...overrides,
  };
}

describe('RelatedRecruits（関連する求人）', () => {
  it('0 件なら、節ごと（見出しも説明も）出さない', () => {
    const { container } = render(<RelatedRecruits jobs={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('ページ: 見出し h2「関連する求人」の節に、一覧と同じカード（RecruitCard）を、渡された順に並べる。カードの題名は h3', () => {
    const { container } = render(<RelatedRecruits jobs={[job(8), job(9), job(5)]} />);
    const section = screen.getByRole('region', { name: '関連する求人' });
    expect(within(section).getByRole('heading', { level: 2, name: '関連する求人' })).toBeInTheDocument();
    expect(container.querySelectorAll('.related-list article.card')).toHaveLength(3);
    expect(within(section).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['職種 8', '職種 9', '職種 5']);
    // カードが h2 のままだと、節の見出しと同じ階層になる（階層が崩れる）。h2 は節の 1 つだけ
    expect(within(section).getAllByRole('heading', { level: 2 })).toHaveLength(1);
  });

  it('ページ: カードのリンクは、通常の <a>（求人の全ページへ。パネルで横取りさせない）。クエリは付けない', () => {
    render(<RelatedRecruits jobs={[job(8)]} />);
    const link = screen.getByRole('link', { name: '職種 8' });
    expect(link).toHaveAttribute('href', '/recruits/8');
    expect(link.tagName).toBe('A');
  });

  it('パネル（inPanel）: 見出しは h3、カードの題名は h4（パネルの題名 h2・ブロック h3 の下の階層）。カードの題名に h2 は出ない', () => {
    render(<RelatedRecruits jobs={[job(8), job(9)]} inPanel />);
    const section = screen.getByRole('region', { name: '関連する求人' });
    expect(within(section).getByRole('heading', { level: 3, name: '関連する求人' })).toBeInTheDocument();
    expect(within(section).getAllByRole('heading', { level: 4 }).map((h) => h.textContent)).toEqual(['職種 8', '職種 9']);
    expect(within(section).queryByRole('heading', { level: 2 })).toBeNull();
    expect(screen.getByRole('link', { name: '職種 8' })).toHaveAttribute('href', '/recruits/8');
  });

  it('文は、並べ方の説明だけ（「近い求人だけ」「機械学習・AI」「最近」とは書かない）。理由を添える', () => {
    render(<RelatedRecruits jobs={[job(8)]} />);
    const note = screen.getByText(/優先して並べています/);
    expect(note.textContent).toContain('この求人を見た人がほかに見ている求人');
    expect(note.textContent).toContain('雇用形態・エリア・職種の近い求人');
    expect(document.body.textContent).not.toMatch(/機械学習|AI|最近/);
  });

  it('カードは、見出しを持つ節（aria-labelledby）の中にある。節の名前は、見出しの文字', () => {
    render(<RelatedRecruits jobs={[job(8)]} />);
    const section = screen.getByRole('region', { name: '関連する求人' });
    const labelledBy = section.getAttribute('aria-labelledby');
    expect(labelledBy).toBeTruthy();
    expect(document.getElementById(labelledBy!)?.textContent).toBe('関連する求人');
  });
});
