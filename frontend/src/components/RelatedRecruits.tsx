import { useId } from 'react';
import type { RecruitSummary } from '../lib/types';
import { RecruitCard } from './RecruitCard';

type Props = {
  jobs: RecruitSummary[];
  /** 一覧に重ねるパネルの中のとき true。見出しは 1 つ下げ（h3・カードは h4）、カードのリンクは Link のまま（押すと、パネルが、その求人に切り替わる）。 */
  inPanel?: boolean;
};

/**
 * 詳細の末尾の「関連する求人」（RecruitDetailView の中。ページとパネルで同じ）。0 件なら、節ごと出さない。
 * 順位は API が決める（docs/recommendation.md）: 「同じ人が一緒に見た数」→「雇用形態・エリア・職種の一致の数」→ ID の順。
 * 閲覧が少ないうちは、一緒に見た数がほとんど 0 で、条件の近い順になる。1 つも合わない求人が、後ろに入ることもある。
 * なので文は、「近い求人だけ」とは書かず、「優先して並べている」とする（並べ方の説明であり、全件が近いとは言っていない）。機械学習は使っていないので、そのようにも書かない。
 * カードは一覧と同じ RecruitCard。パネルの中は、パネルの幅（約 380〜520px）でも崩れない小さな並び（globals.css の .related-list）。
 * ページ（inPanel でない）のカードは、通常の <a>（全ページで開く）。Link だと、一覧のカードと同じく、パネルで横取りして開いてしまい、後ろに開いたままの求人と食い違うため。
 */
export function RelatedRecruits({ jobs, inPanel = false }: Props) {
  const headingId = useId();
  if (jobs.length === 0) return null;
  const Heading = inPanel ? 'h3' : 'h2';
  return (
    <section className="related" aria-labelledby={headingId}>
      <Heading id={headingId}>関連する求人</Heading>
      <p className="related-note">この求人を見た人がほかに見ている求人や、雇用形態・エリア・職種の近い求人を、優先して並べています。</p>
      <div className="related-list">
        {jobs.map((job) => (
          <RecruitCard key={job.id} job={job} query="" headingLevel={inPanel ? 4 : 3} plainLinks={!inPanel} />
        ))}
      </div>
    </section>
  );
}
