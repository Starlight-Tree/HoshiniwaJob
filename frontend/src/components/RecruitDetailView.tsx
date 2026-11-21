import Image from 'next/image';
import { FALLBACK_IMAGE } from '../lib/fallback-image';
import { payOf } from '../lib/format';
import type { RecruitDetail, RecruitSummary } from '../lib/types';
import { RelatedRecruits } from './RelatedRecruits';

type Props = {
  job: RecruitDetail;
  /** 題名の見出しのレベル。詳細ページは 1（既定）。一覧に重ねるパネルは 2（一覧の見出し h1 の下の、カードの題名と同じ階層）。本文のブロックの見出しは、その 1 つ下。 */
  headingLevel?: 1 | 2;
  /** ヒーロー画像・ギャラリーの sizes。既定はページの幅（760px まで）の値。パネルは、パネルの幅に合わせた値を渡す。 */
  heroSizes?: string;
  gallerySizes?: string;
  /** パネルが、開いたときに見出しへフォーカスを移せるようにする（tabIndex=-1 と、探すための印 data-panel-heading を付ける）。 */
  focusHeading?: boolean;
  /** 末尾の「関連する求人」（API の /related）。無い・空なら、節ごと出さない。headingLevel が 2（パネル）のときは、パネルの中の並び・見出しの階層になる。 */
  related?: RecruitSummary[];
};

/** 仕様表の行。値が無い項目（null・空文字）は、行ごと出さない。 */
export function specRows(job: RecruitDetail): [string, string][] {
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
  return rows.filter((row): row is [string, string] => row[1] !== null && row[1] !== '');
}

/**
 * 求人の詳細の本体（法人名・題名・画像・仕様表・各ブロック・関連する求人）。詳細ページ（recruits/[id]/page.tsx）と、一覧に重ねるパネル（RecruitPanel の中）で同じものを出す。
 * 戻るリンクや枠（main・パネル）は、使う側が持つ。画像は API が返す（承認済みのものだけ）。ヒーローは API が決める。無ければ共通の画像。
 */
export function RecruitDetailView({
  job,
  headingLevel = 1,
  heroSizes = '(max-width: 808px) 100vw, 760px',
  gallerySizes = '(max-width: 808px) 50vw, 240px',
  focusHeading = false,
  related = [],
}: Props) {
  const Title = headingLevel === 1 ? 'h1' : 'h2';
  const BlockTitle = headingLevel === 1 ? 'h2' : 'h3';
  const hero = job.hero_image ? { src: job.hero_image.url, alt: job.hero_image.alt, width: job.hero_image.width, height: job.hero_image.height } : FALLBACK_IMAGE;
  const more = job.images.filter((image) => image.id !== job.hero_image?.id);
  const rows = specRows(job);

  return (
    <>
      <p className="card-corporate">{job.corporate}</p>
      <Title {...(focusHeading ? { tabIndex: -1, 'data-panel-heading': '' } : {})}>{job.category}</Title>

      <Image src={hero.src} alt={hero.alt} width={hero.width} height={hero.height} sizes={heroSizes} priority className="detail-hero" />
      {more.length > 0 ? (
        <ul className="detail-gallery" aria-label="ほかの画像">
          {more.map((image) => (
            <li key={image.id}>
              <Image src={image.url} alt={image.alt} width={image.width} height={image.height} sizes={gallerySizes} />
            </li>
          ))}
        </ul>
      ) : null}

      <dl className="spec">
        {rows.map(([label, value]) => (
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
            <BlockTitle>{title}</BlockTitle>
            <p>{body}</p>
          </section>
        ) : null,
      )}

      <RelatedRecruits jobs={related} inPanel={headingLevel === 2} />
    </>
  );
}
