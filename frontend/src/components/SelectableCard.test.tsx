import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { RecruitSummary } from '../lib/types';
import { SelectableCard } from './SelectableCard';

const nav = vi.hoisted(() => ({ pathname: '/' }));
vi.mock('next/navigation', () => ({ usePathname: () => nav.pathname }));

function job(overrides: Partial<RecruitSummary> = {}): RecruitSummary {
  return {
    id: 7,
    corporate: '星庭ワークス',
    category: '温室の見習い',
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

beforeEach(() => {
  nav.pathname = '/';
});

describe('SelectableCard の選択状態', () => {
  it('その求人の詳細パネルが開いている（URL が /recruits/<id>）ときだけ、aria-current="true"', () => {
    nav.pathname = '/recruits/7';
    const { container } = render(<SelectableCard job={job()} query="area=3" />);
    expect(container.querySelector('.card-slot')).toHaveAttribute('aria-current', 'true');
  });

  it.each(['/', '/diagnosis', '/recruits/8', '/recruits/70', '/recruits/7/images'])('%s では、選択状態にしない', (pathname) => {
    nav.pathname = pathname;
    const { container } = render(<SelectableCard job={job()} query="" />);
    expect(container.querySelector('.card-slot')).not.toHaveAttribute('aria-current');
  });

  it('カードの中身は RecruitCard のまま（リンクは題名の 1 つで、行き先はクエリ付き）。包みに、フォーカスを戻すための求人の id を持つ', () => {
    nav.pathname = '/recruits/7';
    const { container } = render(<SelectableCard job={job()} query="area=3" />);
    expect(container.querySelector('.card-slot')).toHaveAttribute('data-recruit-id', '7');
    expect(container.querySelector('.card-slot > article.card')).not.toBeNull();
    expect(screen.getAllByRole('link')).toHaveLength(1);
    expect(screen.getByRole('link', { name: '温室の見習い' })).toHaveAttribute('href', '/recruits/7?area=3');
  });
});
