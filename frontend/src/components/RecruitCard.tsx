import Image from 'next/image';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { FALLBACK_IMAGE } from '../lib/fallback-image';
import { payOf } from '../lib/format';
import type { RecruitSummary } from '../lib/types';

type Props = {
  job: RecruitSummary;
  query: string;
  /** 題名の見出しのレベル。既定は 2（一覧・診断の結果）。詳細の中の「関連する求人」やおすすめの帯は、その節の見出しの 1 つ下にする（3・4）。 */
  headingLevel?: 2 | 3 | 4;
  /** true のとき、リンクを通常の <a> にする（全ページで開く）。詳細ページの「関連する求人」で使う: Link だと、一覧のカードと同じく、パネルで横取りして開いてしまうため。 */
  plainLinks?: boolean;
};

function CardLink({ href, plain, children, ...rest }: { href: string; plain: boolean; children: ReactNode; className?: string; tabIndex?: number; 'aria-hidden'?: true }) {
  return plain ? (
    <a href={href} {...rest}>
      {children}
    </a>
  ) : (
    <Link href={href} {...rest}>
      {children}
    </Link>
  );
}

export function RecruitCard({ job, query, headingLevel = 2, plainLinks = false }: Props) {
  const Heading = `h${headingLevel}` as const;
  const pay = payOf(job);
  const href = `/recruits/${job.id}${query ? `?${query}` : ''}`;
  const tags = [...job.employments, ...job.areas, ...job.stations];
  const thumb = job.hero_image ? { src: job.hero_image.url, width: job.hero_image.width, height: job.hero_image.height } : FALLBACK_IMAGE;
  return (
    <article className="card">
      {/* カード全体が押せる: 題名のリンクを、CSS の ::after でカード全体に広げる（リンクは 1 つのまま。支援技術には題名の名前で 1 回だけ出る）。 */}
      {/* サムネは装飾。題名のリンクが同じ行き先を持つので、支援技術には二重に出さず、Tab の順にも入れない。画像が無い求人は、詳細と同じ共通の雰囲気画像を出す（詳細に画像があるのに一覧だけ空きになるのを避ける） */}
      <CardLink href={href} plain={plainLinks} tabIndex={-1} aria-hidden className="card-thumb">
        <Image src={thumb.src} alt="" width={thumb.width} height={thumb.height} sizes="(max-width: 567px) calc(100vw - 98px), 160px" />
      </CardLink>
      <div className="card-main">
        <p className="card-corporate">{job.corporate ?? '（法人名なし）'}</p>
        <Heading>
          <CardLink href={href} plain={plainLinks}>
            {job.category ?? '（職種名なし）'}
          </CardLink>
        </Heading>
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
        <div className="card-pay">
          <p className="pay-label">{pay.label}</p>
          <p className="pay-value">
            {pay.amount}
            {pay.unit ? <span className="pay-unit">{pay.unit}</span> : null}
          </p>
        </div>
        {/* 押せることの手がかり。リンクは題名の 1 つだけ（::after でカード全体に広げている）なので、これは飾り */}
        <span className="card-arrow" aria-hidden="true">
          ›
        </span>
      </div>
    </article>
  );
}
