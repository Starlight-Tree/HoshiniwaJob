import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { ApiError, fetchGardenRecruits, fetchGardenSummary } from '../../src/lib/api';
import { gardenToken } from '../../src/lib/session';
import type { GardenRecruitItem, GardenSummary } from '../../src/lib/types';

export const dynamic = 'force-dynamic';
export const metadata: Metadata = { title: '園の管理' };

export default async function GardenDashboardPage() {
  const token = await gardenToken();
  if (!token) redirect('/garden/login');

  let summary: GardenSummary;
  let recruits: GardenRecruitItem[];
  try {
    [summary, recruits] = await Promise.all([fetchGardenSummary(token), fetchGardenRecruits(token)]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect('/garden/login');
    return (
      <main className="page">
        <p className="notice" role="alert">
          ただいま利用できません。しばらくしてから、もう一度お試しください
        </p>
      </main>
    );
  }

  return (
    <main className="page">
      <h1 className="garden-title">{summary.corporate}</h1>
      <p className="garden-email">{summary.email}</p>
      <section aria-labelledby="garden-recruits">
        <h2 id="garden-recruits" className="garden-heading">
          掲載している求人
        </h2>
        <dl className="garden-stats">
          <div>
            <dt>表示中</dt>
            <dd>
              <strong>{summary.displayed}</strong> 件
            </dd>
          </div>
          <div>
            <dt>非表示</dt>
            <dd>
              <strong>{summary.hidden}</strong> 件
            </dd>
          </div>
        </dl>
      </section>
      <section aria-labelledby="garden-images" className="garden-images">
        <h2 id="garden-images" className="garden-heading">
          求人の画像
        </h2>
        <ul className="garden-recruit-list">
          {recruits.map((r) => (
            <li key={r.id}>
              <Link href={`/garden/recruits/${r.id}/images`} className="text-link">
                {r.category ?? `求人 ${r.id}`}
              </Link>
              <span className="garden-email">
                {' '}
                {r.is_displayed ? '表示中' : '非表示'}・画像 {r.image_count} 枚（公開中 {r.approved_count} 枚）
              </span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
