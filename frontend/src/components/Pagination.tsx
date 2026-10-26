import Link from 'next/link';
import { hrefFor, type Selection } from '../lib/search';

/** 表示するページ番号。前後 2 ページと、最初・最後。間は null（… で省略）。 */
export function pageWindow(page: number, last: number): (number | null)[] {
  const wanted = new Set([1, last, page - 2, page - 1, page, page + 1, page + 2].filter((n) => n >= 1 && n <= last));
  const sorted = [...wanted].sort((a, b) => a - b);
  const out: (number | null)[] = [];
  sorted.forEach((n, i) => {
    const prev = sorted[i - 1];
    if (prev !== undefined && n - prev > 1) out.push(null);
    out.push(n);
  });
  return out;
}

export function Pagination({ selection, last }: { selection: Selection; last: number }) {
  if (last <= 1) return null;
  const at = (page: number) => hrefFor({ ...selection, page });
  return (
    <nav className="pagination" aria-label="ページ">
      {selection.page > 1 ? (
        <Link href={at(selection.page - 1)} className="page-link wide">
          前へ
        </Link>
      ) : null}
      {pageWindow(selection.page, last).map((n, i) =>
        n === null ? (
          <span key={`gap-${i}`} className="page-gap" aria-hidden="true">
            …
          </span>
        ) : (
          <Link
            key={n}
            href={at(n)}
            className="page-link"
            aria-current={n === selection.page ? 'page' : undefined}
            aria-label={`${n} ページ`}
          >
            {n}
          </Link>
        ),
      )}
      {selection.page < last ? (
        <Link href={at(selection.page + 1)} className="page-link wide">
          次へ
        </Link>
      ) : null}
    </nav>
  );
}
