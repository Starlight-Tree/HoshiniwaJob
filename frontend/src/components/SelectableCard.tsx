'use client';

import { usePathname } from 'next/navigation';
import { RecruitCard } from './RecruitCard';
import type { RecruitSummary } from '../lib/types';

/**
 * 求人のカード（RecruitCard）を包み、その求人の詳細パネルが開いている間（URL が /recruits/<このカードの id>）だけ、選択状態にする。
 * 選択状態は aria-current="true" と、枠・背景（globals.css の .card-slot）。カードの中身（リンクは題名の 1 つだけ）は変えない。
 * 一覧（/）と診断の結果で使う。パネルが開くのは、画面の中でカードを押したあと（ハイドレーション済み）だけなので、サーバーの出力は常に未選択でよい。
 * data-recruit-id は、パネルを閉じたときに、押したカードの題名のリンク（h2 の中）へフォーカスを戻すための目印（RecruitPanel）。
 * 「あなたへのおすすめ」の帯のカードは、同じ求人のカードが一覧にもありうるので、returnFocus={false} にして目印を付けない（戻す先が一覧のカードにずれ、画面が飛ぶのを防ぐ）。
 */
export function SelectableCard({
  job,
  query,
  headingLevel,
  returnFocus = true,
}: {
  job: RecruitSummary;
  query: string;
  /** 題名の見出しのレベル（RecruitCard へ渡す）。既定は 2。 */
  headingLevel?: 2 | 3 | 4;
  returnFocus?: boolean;
}) {
  const selected = usePathname() === `/recruits/${job.id}`;
  return (
    <div className="card-slot" data-recruit-id={returnFocus ? job.id : undefined} aria-current={selected ? 'true' : undefined}>
      <RecruitCard job={job} query={query} headingLevel={headingLevel} />
    </div>
  );
}
