import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { cache } from 'react';
import { ApiError, fetchRecruit } from '../../../../src/lib/api';
import { payOf } from '../../../../src/lib/format';
import { hrefFor, parseSelection } from '../../../../src/lib/search';

export const dynamic = 'force-dynamic';

// 画像が 1 枚も公開されていない求人に使う、共通の雰囲気画像（Git で管理するもの）
const FALLBACK_IMAGE = {
  src: '/images/generated/job-detail-sample.jpg',
  alt: '環軌道植物園の温室のイメージ',
  width: 1376,
  height: 768,
};

type Props = {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

// generateMetadata と本体で同じ求人を 2 回読まないよう、同じ描画の中では結果を使い回す
const load = cache(async (id: string) => {
  const n = Number(id);
  if (!Number.isInteger(n) || n < 1) notFound();
  try {
    return await fetchRecruit(n);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return null;
  }
});

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const job = await load((await params).id);
  return { title: job ? `${job.category ?? '求人'}（${job.corporate ?? ''}）` : '求人' };
}

export default async function RecruitPage({ params, searchParams }: Props) {
  const job = await load((await params).id);
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

  // 画像は API が返す（承認済みのものだけ）。ヒーローは API が決める。無ければ共通の画像
  const hero = job.hero_image ? { src: job.hero_image.url, alt: job.hero_image.alt, width: job.hero_image.width, height: job.hero_image.height } : FALLBACK_IMAGE;
  const more = job.images.filter((image) => image.id !== job.hero_image?.id);
  const pay = payOf(job);
  const hours = job.start_time && job.end_time ? `${job.start_time}〜${job.end_time}` : null;
  const rows: [string, string | null][] = [
    ['法人名', job.corporate],
    ['職種', job.category],
    ['雇用形態', job.employments.join('、') || null],
    [pay.label, pay.value],
    ['勤務地', [job.place, ...job.areas].filter(Boolean).join('　') || null],
    ['最寄りの乗り場', job.stations.join('、') || null],
    ['勤務時間', hours],
    ['勤務日', job.workday],
    ['保険', job.insurance],
  ];

  return (
    <main className="page detail">
      <p>
        <Link href={back} className="text-link">
          ← 検索結果にもどる
        </Link>
      </p>
      <p className="card-corporate">{job.corporate}</p>
      <h1>{job.category}</h1>

      <Image
        src={hero.src}
        alt={hero.alt}
        width={hero.width}
        height={hero.height}
        sizes="(max-width: 808px) 100vw, 760px"
        priority
        className="detail-hero"
      />
      {more.length > 0 ? (
        <ul className="detail-gallery" aria-label="ほかの画像">
          {more.map((image) => (
            <li key={image.id}>
              <Image src={image.url} alt={image.alt} width={image.width} height={image.height} sizes="(max-width: 808px) 50vw, 240px" />
            </li>
          ))}
        </ul>
      ) : null}

      <dl className="spec">
        {rows
          .filter((row): row is [string, string] => row[1] !== null && row[1] !== '')
          .map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
      </dl>

      {[
        ['業務内容', job.comment1],
        ['法人の紹介', job.profile],
        ['給与の備考', job.note1],
        ['勤務時間の備考', job.note2],
        ['勤務日の備考', job.note3],
        ['休日', job.comment2],
        ['福利厚生', job.comment3],
      ].map(([title, body]) =>
        body ? (
          <section key={title} className="detail-block">
            <h2>{title}</h2>
            <p>{body}</p>
          </section>
        ) : null,
      )}
    </main>
  );
}
