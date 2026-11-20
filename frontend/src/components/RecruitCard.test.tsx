import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { RecruitSummary } from '../lib/types';
import { RecruitCard } from './RecruitCard';

const HERO = { id: 'img-1', url: '/media/images/x.jpg', alt: '温室の入口', width: 800, height: 600, mime_type: 'image/jpeg' };

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
    hero_image: HERO,
    ...overrides,
  };
}

describe('RecruitCard のサムネ', () => {
  it('hero_image があると、サムネの img（alt は空）を出す。リンクは装飾（aria-hidden・tabIndex -1）で、題名と同じ行き先', () => {
    const { container } = render(<RecruitCard job={job()} query="area=3" />);
    const img = container.querySelector('.card-thumb img');
    expect(img).not.toBeNull();
    expect(img).toHaveAttribute('alt', '');
    // next/image は src を /_next/image?url=<元の URL（パーセントエンコード）>&w=…&q=… に変える。元の URL が url に入っていることを確かめる
    const src = img?.getAttribute('src') ?? '';
    expect(decodeURIComponent(src)).toContain('/media/images/x.jpg');
    expect(new URL(src, 'http://localhost').searchParams.get('url')).toBe('/media/images/x.jpg');
    expect(img).toHaveAttribute('width', '800');
    expect(img).toHaveAttribute('height', '600');

    const thumb = container.querySelector('a.card-thumb');
    expect(thumb).not.toBeNull();
    expect(thumb).toHaveAttribute('aria-hidden', 'true');
    expect(thumb).toHaveAttribute('tabindex', '-1');
    const title = screen.getByRole('link', { name: '温室の見習い' });
    expect(title).toHaveAttribute('href', '/recruits/7?area=3');
    expect(thumb).toHaveAttribute('href', title.getAttribute('href'));
    expect(container.querySelector('.card-thumb-empty')).toBeNull();
  });

  it('サムネは装飾なので、支援技術に二重に出さない（alt が空の画像も、aria-hidden のリンクも、役割として見えない）', () => {
    render(<RecruitCard job={job()} query="" />);
    expect(screen.queryByRole('img')).toBeNull();
    // リンクは題名の 1 つだけ（それをカード全体に広げている）。サムネのリンクは数えない
    expect(screen.getAllByRole('link')).toHaveLength(1);
    expect(screen.queryByText('詳細を見る')).toBeNull();
  });

  it('カード全体が押せる: 題名のリンクがカードの中に 1 つあり、押せることの矢印は飾り（aria-hidden）', () => {
    const { container } = render(<RecruitCard job={job()} query="" />);
    expect(container.querySelectorAll('article.card h2 a')).toHaveLength(1);
    const arrow = container.querySelector('.card-arrow');
    expect(arrow).toHaveAttribute('aria-hidden', 'true');
    expect(arrow?.textContent).toBe('›');
  });

  it('hero_image が null なら、img は出さず、同じ大きさの空き枠（card-thumb-empty）を出す', () => {
    const { container } = render(<RecruitCard job={job({ hero_image: null })} query="" />);
    expect(container.querySelector('img')).toBeNull();
    const empty = container.querySelector('div.card-thumb.card-thumb-empty');
    expect(empty).not.toBeNull();
    expect(empty).toHaveAttribute('aria-hidden', 'true');
    expect(container.querySelector('a.card-thumb')).toBeNull();
  });

  it('サムネは、card-main より前（カードの先頭）に置く', () => {
    const { container } = render(<RecruitCard job={job()} query="" />);
    const children = [...(container.querySelector('article.card')?.children ?? [])].map((el) => el.className);
    expect(children[0]).toContain('card-thumb');
    expect(children[1]).toBe('card-main');
  });
});

describe('RecruitCard の給与', () => {
  it('読み上げ・textContent は今までと同じで、単位は .pay-unit に入る', () => {
    const { container } = render(<RecruitCard job={job()} query="" />);
    const value = container.querySelector('.pay-value');
    expect(value?.textContent).toBe('180,000〜240,000ルミ');
    const unit = value?.querySelector('.pay-unit');
    expect(unit?.textContent).toBe('ルミ');
    expect(screen.getByText('月給')).toBeInTheDocument();
  });

  it('応相談では .pay-unit を出さない', () => {
    const { container } = render(<RecruitCard job={job({ pay_min: null, pay_max: null })} query="" />);
    const value = container.querySelector('.pay-value');
    expect(value?.textContent).toBe('応相談');
    expect(container.querySelector('.pay-unit')).toBeNull();
  });
});
