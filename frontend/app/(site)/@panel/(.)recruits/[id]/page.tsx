import type { Metadata } from 'next';
import { RecruitDetailView } from '../../../../../src/components/RecruitDetailView';
import { RecruitPanel } from '../../../../../src/components/RecruitPanel';
import { loadRecruit } from '../../../../../src/lib/load-recruit';

export const dynamic = 'force-dynamic';

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const job = await loadRecruit((await params).id);
  return { title: job ? `${job.category ?? '求人'}（${job.corporate ?? ''}）` : '求人' };
}

// 一覧のカードを押したときに、同じ URL（/recruits/ID）を、全ページの代わりに一覧の右のパネルで開く（インターセプト）。
// 直接開く・再読み込みしたときは、この画面は使われず、recruits/[id]/page.tsx の全ページが出る
export default async function RecruitPanelPage({ params }: Props) {
  const job = await loadRecruit((await params).id);

  if (job === null) {
    return (
      <RecruitPanel>
        <div className="notice" role="alert">
          <p>求人を読み込めませんでした。しばらくしてから、もう一度開いてください。</p>
        </div>
      </RecruitPanel>
    );
  }

  return (
    <RecruitPanel>
      <RecruitDetailView job={job} headingLevel={2} focusHeading heroSizes="(max-width: 1279px) 100vw, 760px" gallerySizes="(max-width: 1279px) 50vw, 240px" />
    </RecruitPanel>
  );
}
