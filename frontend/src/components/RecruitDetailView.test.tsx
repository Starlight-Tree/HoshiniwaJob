import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { RecruitDetail, RecruitSummary } from '../lib/types';
import { RecruitDetailView, specRows } from './RecruitDetailView';

const IMAGE = (id: string) => ({ id, url: `/media/images/${id}.jpg`, alt: `画像 ${id}`, width: 800, height: 600, mime_type: 'image/jpeg' });

function detail(overrides: Partial<RecruitDetail> = {}): RecruitDetail {
  return {
    id: 7,
    corporate: '星庭ワークス',
    category: '温室の見習い',
    salary: 2,
    pay_min: 180000,
    pay_max: 240000,
    comment1: '蔓の剪定をお任せします。',
    note1: null,
    formfile: null,
    areas: ['北の丘'],
    stations: ['第一環ステーション'],
    occupations: [],
    employments: ['常勤', '短時間'],
    hero_image: IMAGE('hero'),
    images: [IMAGE('hero'), IMAGE('more')],
    profile: null,
    place: '第一温室',
    note2: null,
    note3: null,
    comment2: null,
    comment3: null,
    workday: '週 4 日',
    insurance: null,
    start_time: '09:00',
    end_time: '17:30',
    ...overrides,
  };
}

describe('specRows（仕様表の行）', () => {
  it('値のある項目だけを、決まった順に出す', () => {
    expect(specRows(detail())).toEqual([
      ['法人名', '星庭ワークス'],
      ['職種', '温室の見習い'],
      ['雇用形態', '常勤、短時間'],
      ['月給', '180,000〜240,000ルミ'],
      ['勤務地', '第一温室　北の丘'],
      ['最寄りの乗り場', '第一環ステーション'],
      ['勤務時間', '09:00〜17:30'],
      ['勤務日', '週 4 日'],
    ]);
  });

  it('空の項目（null・空の一覧・片方だけの時刻・空文字）は、行ごと出さない', () => {
    const rows = specRows(detail({ corporate: null, employments: [], place: null, areas: [], stations: [], start_time: '09:00', end_time: null, workday: '', insurance: null }));
    expect(rows.map(([label]) => label)).toEqual(['職種', '月給']);
  });
});

describe('RecruitDetailView', () => {
  it('仕様表に、値のある行だけが並ぶ（空の dt・dd を出さない）', () => {
    const { container } = render(<RecruitDetailView job={detail({ insurance: null, workday: null })} />);
    const labels = [...container.querySelectorAll('dl.spec dt')].map((dt) => dt.textContent);
    expect(labels).toEqual(['法人名', '職種', '雇用形態', '月給', '勤務地', '最寄りの乗り場', '勤務時間']);
    for (const dd of container.querySelectorAll('dl.spec dd')) expect((dd.textContent ?? '').trim()).not.toBe('');
  });

  it('ページ（既定）: 題名は h1、本文のブロックは h2。ブロックは本文のある項目だけ', () => {
    render(<RecruitDetailView job={detail({ profile: '宇宙の植物園です。', comment2: null })} />);
    expect(screen.getByRole('heading', { level: 1, name: '温室の見習い' })).not.toHaveAttribute('tabindex');
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual(['業務内容', '法人の紹介']);
    expect(screen.queryByRole('heading', { level: 3 })).toBeNull();
    expect(screen.getByText('蔓の剪定をお任せします。')).toBeInTheDocument();
  });

  it('パネル（headingLevel=2）: 題名は h2、ブロックは h3。focusHeading で、見出しにフォーカスの受け口（tabIndex=-1）と印が付く', () => {
    render(<RecruitDetailView job={detail()} headingLevel={2} focusHeading />);
    const title = screen.getByRole('heading', { level: 2, name: '温室の見習い' });
    expect(title).toHaveAttribute('tabindex', '-1');
    expect(title).toHaveAttribute('data-panel-heading');
    expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
    expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['業務内容']);
  });

  it('画像: ヒーローと、それ以外のギャラリー（ヒーローは重ねない）。sizes は props で切り替えられる', () => {
    const { container } = render(<RecruitDetailView job={detail()} heroSizes="100vw" gallerySizes="50vw" />);
    const hero = container.querySelector('img.detail-hero');
    expect(hero).toHaveAttribute('alt', '画像 hero');
    expect(hero).toHaveAttribute('sizes', '100vw');
    const gallery = screen.getByRole('list', { name: 'ほかの画像' });
    const images = within(gallery).getAllByRole('img');
    expect(images).toHaveLength(1);
    expect(images[0]).toHaveAttribute('alt', '画像 more');
    expect(images[0]).toHaveAttribute('sizes', '50vw');
  });

  it('画像が無い求人は、共通の雰囲気画像を出し、ギャラリーは出さない', () => {
    const { container } = render(<RecruitDetailView job={detail({ hero_image: null, images: [] })} />);
    expect(container.querySelector('img.detail-hero')).toHaveAttribute('alt', '環軌道植物園の温室のイメージ');
    expect(screen.queryByRole('list', { name: 'ほかの画像' })).toBeNull();
  });
});

describe('RecruitDetailView の「関連する求人」', () => {
  const related = (id: number): RecruitSummary => ({
    id,
    corporate: '星庭ワークス',
    category: `関連の職種 ${id}`,
    salary: 2,
    pay_min: 180000,
    pay_max: 240000,
    comment1: null,
    note1: null,
    formfile: null,
    areas: [],
    stations: [],
    occupations: [],
    employments: [],
    hero_image: null,
  });

  it('渡さない・空なら、節ごと出さない（既存の見出しも変わらない）', () => {
    const { rerender } = render(<RecruitDetailView job={detail()} />);
    expect(screen.queryByRole('region', { name: '関連する求人' })).toBeNull();
    rerender(<RecruitDetailView job={detail()} related={[]} />);
    expect(screen.queryByText('関連する求人')).toBeNull();
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual(['業務内容']);
  });

  it('ページ: 本文のブロックの後ろ（末尾）に、h2「関連する求人」と、h3 の題名のカードが並ぶ', () => {
    const { container } = render(<RecruitDetailView job={detail()} related={[related(8), related(9)]} />);
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual(['業務内容', '関連する求人']);
    const section = screen.getByRole('region', { name: '関連する求人' });
    expect(section.previousElementSibling?.className).toBe('detail-block');
    expect(container.lastElementChild).toBe(section);
    expect(within(section).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['関連の職種 8', '関連の職種 9']);
  });

  it('パネル（headingLevel=2）: 見出しは h3、カードの題名は h4。パネルの題名（h2）は 1 つのまま', () => {
    render(<RecruitDetailView job={detail()} headingLevel={2} focusHeading related={[related(8)]} />);
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual(['温室の見習い']);
    expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['業務内容', '関連する求人']);
    expect(screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent)).toEqual(['関連の職種 8']);
  });
});

