import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { parseSelection } from '../lib/search';
import { Pagination, pageWindow } from './Pagination';

describe('pageWindow', () => {
  it('少ないときは全部、多いときは前後 2 ページと両端で、間を … にする', () => {
    expect(pageWindow(1, 3)).toEqual([1, 2, 3]);
    expect(pageWindow(10, 20)).toEqual([1, null, 8, 9, 10, 11, 12, null, 20]);
    expect(pageWindow(1, 20)).toEqual([1, 2, 3, null, 20]);
  });
});

describe('Pagination', () => {
  it('1 ページだけなら何も出さない', () => {
    const { container } = render(<Pagination selection={parseSelection({})} last={1} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('今のページに aria-current を付け、リンクに条件を引き継ぐ', () => {
    render(<Pagination selection={parseSelection({ area: '3', page: '2' })} last={3} />);
    expect(screen.getByRole('link', { name: '2 ページ' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: '3 ページ' })).toHaveAttribute('href', '/?area=3&page=3');
    expect(screen.getByRole('link', { name: '前へ' })).toHaveAttribute('href', '/?area=3');
    expect(screen.getByRole('link', { name: '次へ' })).toHaveAttribute('href', '/?area=3&page=3');
  });
});
