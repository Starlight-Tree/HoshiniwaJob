'use client';

import { usePathname } from 'next/navigation';
import { RecruitCard } from './RecruitCard';
import type { RecruitSummary } from '../lib/types';

/**
 * 求人のカード（RecruitCard）を包み、その求人の詳細パネルが開いている間（URL が /recruits/<このカードの id>）だけ、選択状態にする。
 * 選択状態は aria-current="true" と、枠・背景（globals.css の .card-slot）。カードの中身（リンクは題名の 1 つだけ）は変えない。
 * 一覧（/）と診断の結果で使う。パネルが開くのは、画面の中でカードを押したあと（ハイドレーション済み）だけなので、サーバーの出力は常に未選択でよい。
 * data-recruit-id は、パネルを閉じたときに、押したカードの題名のリンクへフォーカスを戻すための目印。
 */
export function SelectableCard({ job, query }: { job: RecruitSummary; query: string }) {
  const selected = usePathname() === `/recruits/${job.id}`;
  return (
    <div className="card-slot" data-recruit-id={job.id} aria-current={selected ? 'true' : undefined}>
      <RecruitCard job={job} query={query} />
    </div>
  );
}
