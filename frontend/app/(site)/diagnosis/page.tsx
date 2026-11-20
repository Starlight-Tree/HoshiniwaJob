import Link from 'next/link';
import { DiagnosisForm } from '../../../src/components/DiagnosisForm';
import { RecruitCard } from '../../../src/components/RecruitCard';
import { fetchMaster, fetchRecruits } from '../../../src/lib/api';
import { isSubmitted, parseAnswers, QUESTION_LABEL, rank, reasonOf, selectionOf, wantedOf } from '../../../src/lib/diagnosis';
import { hrefFor, parseSelection } from '../../../src/lib/search';
import type { Master, RecruitSummary } from '../../../src/lib/types';

export const dynamic = 'force-dynamic';

// 結果に出す件数。これより多く合う求人は、「この条件で絞り込む」から、求人検索で見る
const MAX_SHOWN = 6;
// API が 1 回で返す上限（per_page の最大）。今の求人は 30 件ほどで収まる。超えたら、先頭の 50 件だけを診断の対象にする
const POOL = 50;

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default async function DiagnosisPage({ searchParams }: Props) {
  const params = await searchParams;
  const answers = parseAnswers(params);
  const submitted = isSubmitted(params);

  let data: { master: Master; jobs: RecruitSummary[] } | null = null;
  try {
    const [master, page] = await Promise.all([fetchMaster(), fetchRecruits(parseSelection({}), POOL)]);
    data = { master, jobs: page.items };
  } catch {
    // 例外の文面は画面に出さない（API のアドレスなどが混ざるため）。固定の文だけ出す
    data = null;
  }

  if (data === null) {
    return (
      <main className="page">
        <h1>3 つの質問で、求人を診断</h1>
        <div className="notice" role="alert">
          <p>診断を読み込めませんでした。しばらくしてから、もう一度開いてください。</p>
        </div>
      </main>
    );
  }

  const { master, jobs } = data;
  const wanted = submitted ? wantedOf(answers, master) : [];
  const matches = rank(jobs, answers, master);
  const shown = matches.slice(0, MAX_SHOWN);

  return (
    <main className="page diagnosis">
      <h1>3 つの質問で、求人を診断</h1>
      <p className="diagnosis-lead">
        希望に近い求人を、合う条件の多い順に出します。こだわらない質問は、そのままで大丈夫です。AI や学習は使わず、条件が合うかを数えるだけの、簡単な診断です。
      </p>

      <DiagnosisForm master={master} answers={answers} />

      {submitted ? (
        <section id="result" className="diagnosis-result" aria-label="診断の結果">
          {wanted.length === 0 ? (
            <div className="notice">
              <p>1 つ以上、条件を選んでから「診断する」を押してください。</p>
            </div>
          ) : (
            <>
              <h2>
                あなたにおすすめの求人 <span className="range">（{matches.length} 件が一致。上位 {shown.length} 件）</span>
              </h2>
              <p className="diagnosis-picked">
                選んだ条件：{wanted.map((w) => `${QUESTION_LABEL[w.kind]}＝${w.name}`).join('、')}
              </p>
              {shown.length === 0 ? (
                <div className="empty">
                  <h3>条件に合う求人は見つかりませんでした</h3>
                  <p>条件を「こだわらない」に変えて、もう一度診断してみてください。</p>
                </div>
              ) : (
                <div className="diagnosis-list">
                  {shown.map((m) => (
                    <div key={m.job.id} className="match">
                      <p className="match-reason">{reasonOf(m)}</p>
                      <RecruitCard job={m.job} query="" />
                    </div>
                  ))}
                </div>
              )}
              <p className="diagnosis-more">
                <Link className="text-link" href={hrefFor(selectionOf(answers))}>
                  この条件で、求人検索で絞り込む →
                </Link>
              </p>
            </>
          )}
        </section>
      ) : null}
    </main>
  );
}
