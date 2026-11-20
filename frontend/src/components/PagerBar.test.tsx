import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { parseSelection } from '../lib/search';
import { PagerBar, pagerRange } from './PagerBar';

describe('pagerRange', () => {
  it('表示している範囲。最後のページは、残りの件数まで', () => {
    expect(pagerRange(1, 10, 11)).toEqual({ from: 1, to: 10 });
    expect(pagerRange(2, 10, 11)).toEqual({ from: 11, to: 11 });
    expect(pagerRange(1, 10, 0)).toEqual({ from: 0, to: 0 });
  });
});

describe('PagerBar', () => {
  it('0 件のときは出さない', () => {
    const { container } = render(<PagerBar selection={parseSelection({})} last={1} total={0} perPage={10} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('1 ページ目: 範囲と「1 / 2」を出し、前は押せない表示、次は ?page=2 へのリンク', () => {
    render(<PagerBar selection={parseSelection({ area: '3' })} last={2} total={11} perPage={10} />);
    expect(screen.getByRole('navigation', { name: 'ページ移動' })).toBeInTheDocument();
    expect(screen.getByText('1–10 / 11 件')).toBeInTheDocument();
    expect(screen.getByText('1 / 2')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '前のページ' })).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByRole('link', { name: '前のページ' })).not.toHaveAttribute('href');
    expect(screen.getByRole('link', { name: '次のページ' })).toHaveAttribute('href', '/?area=3&page=2');
  });

  it('最後のページ: 次は押せない表示、前は条件を引き継いだリンク（1 ページ目の URL は page なし）', () => {
    render(<PagerBar selection={parseSelection({ area: '3', page: '2' })} last={2} total={11} perPage={10} />);
    expect(screen.getByText('11–11 / 11 件')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '次のページ' })).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByRole('link', { name: '前のページ' })).toHaveAttribute('href', '/?area=3');
  });

  it('1 ページだけのときも、範囲を出す（前後はどちらも押せない）', () => {
    render(<PagerBar selection={parseSelection({})} last={1} total={5} perPage={10} />);
    expect(screen.getByText('1–5 / 5 件')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '前のページ' })).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByRole('link', { name: '次のページ' })).toHaveAttribute('aria-disabled', 'true');
  });
});
