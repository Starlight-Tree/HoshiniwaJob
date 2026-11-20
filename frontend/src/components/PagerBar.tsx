import Link from 'next/link';
import { hrefFor, type Selection } from '../lib/search';

/** 表示している範囲（1 始まり）。0 件のときは両方 0。 */
export function pagerRange(page: number, perPage: number, total: number): { from: number; to: number } {
  if (total === 0) return { from: 0, to: 0 };
  return { from: (page - 1) * perPage + 1, to: Math.min(total, page * perPage) };
}

type Props = { selection: Selection; last: number; total: number; perPage: number };

/**
 * 一覧の下に固定するページ送り（DocuNavi の資料一覧の下端のバーと同じ形）。左に「1–10 / 11 件」、右に ‹ 1 / 2 ›。
 * 前後のページは、?page=N への通常のリンク（URL を共有でき、戻るボタンも使える）。先頭・末尾では、押せない表示にする（aria-disabled）。
 * 1 ページだけのときも出す（いま何件を見ているかが分かる。押せるのは無い）。0 件のときは出さない。
 * 固定は CSS の position: sticky（globals.css の .pager）。一覧の最後まで、画面の下に留まる。
 */
export function PagerBar({ selection, last, total, perPage }: Props) {
  if (total === 0) return null;
  const { from, to } = pagerRange(selection.page, perPage, total);
  const at = (page: number) => hrefFor({ ...selection, page });
  return (
    <nav className="pager" aria-label="ページ移動">
      <span className="pager-range">
        {from}–{to} / {total} 件
      </span>
      <span className="pager-nav">
        {selection.page > 1 ? (
          <Link href={at(selection.page - 1)} className="pager-btn" aria-label="前のページ" rel="prev">
            ‹
          </Link>
        ) : (
          <span className="pager-btn" role="link" aria-disabled="true" aria-label="前のページ">
            ‹
          </span>
        )}
        <span className="pager-pos" aria-live="polite">
          {selection.page} / {last}
        </span>
        {selection.page < last ? (
          <Link href={at(selection.page + 1)} className="pager-btn" aria-label="次のページ" rel="next">
            ›
          </Link>
        ) : (
          <span className="pager-btn" role="link" aria-disabled="true" aria-label="次のページ">
            ›
          </span>
        )}
      </span>
    </nav>
  );
}
