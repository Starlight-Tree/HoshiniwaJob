import type { Metadata } from 'next';
import Link from 'next/link';
import { RecruitDetailView } from '../../../../src/components/RecruitDetailView';
import { loadRecruit } from '../../../../src/lib/load-recruit';
import { hrefFor, parseSelection } from '../../../../src/lib/search';

export const dynamic = 'force-dynamic';

type Props = {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const job = await loadRecruit((await params).id);
  return { title: job ? `${job.category ?? '求人'}（${job.corporate ?? ''}）` : '求人' };
}

// 直接開いた・再読み込みしたときの、これまでどおりの全ページ。一覧から押したときは、同じ URL が一覧の右のパネルで開く（@panel の (.)recruits/[id]）
export default async function RecruitPage({ params, searchParams }: Props) {
  const job = await loadRecruit((await params).id);
  // 一覧から来たときの条件を、「検索結果にもどる」へ引き継ぐ
  const back = hrefFor(parseSelection(await searchParams));

  if (job === null) {
    return (
      <main className="page">
        <p>
          <Link href={back} className="text-link">
            ← 検索結果にもどる
          </Link>
        </p>
        <div className="notice" role="alert">
          <p>求人を読み込めませんでした。しばらくしてから、もう一度開いてください。</p>
        </div>
      </main>
    );
  }

  return (
    <main className="page detail">
      <p>
        <Link href={back} className="text-link">
          ← 検索結果にもどる
        </Link>
      </p>
      <RecruitDetailView job={job} />
    </main>
  );
}
