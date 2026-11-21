import { useId } from 'react';
import type { RecruitSummary } from '../lib/types';
import { SelectableCard } from './SelectableCard';

/**
 * 一覧（トップ）の上の「あなたへのおすすめ」の帯。ログインした求職者にだけ、検索条件が付いていないときに、使う側（app/(site)/page.tsx）が出す。履歴が無い（[]）なら、帯ごと出さない。
 * 選び方は API が決める（docs/recommendation.md）: **これまでに見た求人すべて**（「最近」ではない）をもとに、その人がまだ見ていない求人から、
 * 「見た求人を見た別の人がほかに見ている数」×3 と「雇用形態・エリア・職種の一致の数」の合計が大きい順に選ぶ。得点が 0 の求人は出ない。機械学習は使っていない。
 * 文は、その事実のとおりに書く（「最近見た」とは書かない。AI・学習のことも書かない）。
 * 見た目は、一覧の邪魔をしない小さなタイル（サムネ・タグ・本文は出さず、法人名・題名・給与だけ。globals.css の .recs-list）。
 * カードは一覧と同じ（SelectableCard。押すと、一覧の右のパネルで開く）。見出しは h2、カードの題名は h3。
 */
export function RecommendedRecruits({ jobs }: { jobs: RecruitSummary[] }) {
  const headingId = useId();
  if (jobs.length === 0) return null;
  return (
    <section className="recs" aria-labelledby={headingId}>
      <h2 id={headingId}>あなたへのおすすめ</h2>
      <p className="recs-note">これまでに見た求人をもとに、雇用形態・エリア・職種の近い求人や、同じ求人を見た人がほかに見ている求人を選んでいます。</p>
      <div className="recs-list">
        {jobs.map((job) => (
          <SelectableCard key={job.id} job={job} query="" headingLevel={3} returnFocus={false} />
        ))}
      </div>
    </section>
  );
}
