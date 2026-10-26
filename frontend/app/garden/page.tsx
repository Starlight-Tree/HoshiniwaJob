import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { ApiError, fetchGardenSummary } from '../../src/lib/api';
import { gardenToken } from '../../src/lib/session';
import type { GardenSummary } from '../../src/lib/types';

export const dynamic = 'force-dynamic';
export const metadata: Metadata = { title: '園の管理' };

export default async function GardenDashboardPage() {
  const token = await gardenToken();
  if (!token) redirect('/garden/login');

  let summary: GardenSummary;
  try {
    summary = await fetchGardenSummary(token);
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
    </main>
  );
}
