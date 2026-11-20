import Link from 'next/link';
import { redirect } from 'next/navigation';
import { FilterForm } from '../../src/components/FilterForm';
import { Pagination } from '../../src/components/Pagination';
import { RecruitCard } from '../../src/components/RecruitCard';
import { SelectedChips } from '../../src/components/SelectedChips';
import { fetchFacets, fetchMaster, fetchRecruits } from '../../src/lib/api';
import { shownRange } from '../../src/lib/format';
import { chipsFor, hasConditions, hrefFor, parseSelection, toQuery } from '../../src/lib/search';
import type { Facets, Master, RecruitPage } from '../../src/lib/types';

export const dynamic = 'force-dynamic';

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default async function Home({ searchParams }: Props) {
  const selection = parseSelection(await searchParams);

  let data: { master: Master; facets: Facets; result: RecruitPage } | null = null;
  try {
    const [master, facets, result] = await Promise.all([fetchMaster(), fetchFacets(selection), fetchRecruits(selection)]);
    data = { master, facets, result };
  } catch {
    // 例外の文面は画面に出さない（API のアドレスなどが混ざるため）。固定の文だけ出す
    data = null;
  }

  if (data === null) {
    return (
      <main className="page">
        <h1>宇宙の植物園・ガーデンの求人</h1>
        <div className="notice" role="alert">
          <p>求人を読み込めませんでした。しばらくしてから、もう一度開いてください。</p>
        </div>
      </main>
    );
  }

  const { master, facets, result } = data;
  // 最後のページより先を開いたら、最後のページへ移す
  if (result.total > 0 && result.page > result.last_page) {
    redirect(hrefFor({ ...selection, page: result.last_page }));
  }

  const chips = chipsFor(selection, master);
  const query = toQuery(selection);

  return (
    <main className="page">
      <div className="title-row">
        <h1>宇宙の植物園・ガーデンの求人</h1>
        <p className="result-count" aria-live="polite">
          <strong>{result.total}</strong> 件が見つかりました
          {result.total > 0 ? <span className="range">（{shownRange(result.page, result.per_page, result.total)}）</span> : null}
        </p>
      </div>

      <p className="diagnosis-hint">
        どれを選べばいいか迷ったら、<Link href="/diagnosis">3 つの質問で診断</Link>してみてください。
      </p>

      <FilterForm master={master} facets={facets} selection={selection} />

      <section className="results" aria-label="検索結果">
        <SelectedChips chips={chips} />
        {result.items.length > 0 ? (
          <>
            {result.items.map((job) => (
              <RecruitCard key={job.id} job={job} query={query} />
            ))}
            <Pagination selection={selection} last={result.last_page} />
          </>
        ) : (
          <div className="empty">
            <h2>条件に合う求人は見つかりませんでした</h2>
            {hasConditions(selection) ? (
              <>
                <p>条件を 1 つ外すと、見つかることがあります。上のチップの ✕ で、条件を 1 つずつ外せます。</p>
                <a className="primary-button inline" href="/">
                  条件をすべてクリア
                </a>
              </>
            ) : (
              <p>いま公開している求人はありません。</p>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
