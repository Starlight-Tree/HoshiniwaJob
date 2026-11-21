import type { Metadata } from 'next';
import Link from 'next/link';
import { RecruitDetailView } from '../../../../src/components/RecruitDetailView';
import { RecruitViewRecorder } from '../../../../src/components/RecruitViewRecorder';
import { loadRecruit } from '../../../../src/lib/load-recruit';
import { loadRelated } from '../../../../src/lib/load-related';
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
  const { id } = await params;
  // 関連する求人は、求人と同時に読む（付随なので、取れなければ空）
  const [job, related] = await Promise.all([loadRecruit(id), loadRelated(id)]);
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
      <RecruitDetailView job={job} related={related} />
      {/* ログイン中の求職者のときだけ、開いたあとに、閲覧を 1 回記録する（クライアントの副作用。パネルと同じ） */}
      <RecruitViewRecorder recruitId={job.id} />
    </main>
  );
}
