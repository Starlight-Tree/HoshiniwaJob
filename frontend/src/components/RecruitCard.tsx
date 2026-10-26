import Link from 'next/link';
import { payOf } from '../lib/format';
import type { RecruitSummary } from '../lib/types';

export function RecruitCard({ job, query }: { job: RecruitSummary; query: string }) {
  const pay = payOf(job);
  const href = `/recruits/${job.id}${query ? `?${query}` : ''}`;
  const tags = [...job.employments, ...job.areas, ...job.stations];
  return (
    <article className="card">
      <div className="card-main">
        <p className="card-corporate">{job.corporate ?? '（法人名なし）'}</p>
        <h2>
          <Link href={href}>{job.category ?? '（職種名なし）'}</Link>
        </h2>
        {tags.length > 0 ? (
          <ul className="tags" aria-label="条件">
            {tags.map((tag, i) => (
              <li key={`${tag}-${i}`}>{tag}</li>
            ))}
          </ul>
        ) : null}
        {job.comment1 ? <p className="card-summary">{job.comment1}</p> : null}
      </div>
      <div className="card-side">
        <p className="pay-label">{pay.label}</p>
        <p className="pay-value">{pay.value}</p>
        <Link href={href} className="outline-button">
          詳細を見る
        </Link>
      </div>
    </article>
  );
}
