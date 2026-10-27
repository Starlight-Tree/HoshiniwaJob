import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';
import { moveImageAction, removeImageAction, setHeroAction } from '../../../../../src/actions/garden-images';
import { ImageUploadForm } from '../../../../../src/components/ImageUploadForm';
import { ApiError, fetchGardenRecruitImages } from '../../../../../src/lib/api';
import { gardenToken } from '../../../../../src/lib/session';
import type { GardenImage, GardenRecruitImages } from '../../../../../src/lib/types';

export const dynamic = 'force-dynamic';
export const metadata: Metadata = { title: '求人の画像' };

const STATUS: Record<GardenImage['status'], string> = {
  approved: '公開中',
  pending: '承認待ち（まだ公開されていません）',
  rejected: '却下されました（公開されません）',
  publishing: '公開の準備中',
  uploading: '登録中',
};

export default async function RecruitImagesPage({ params }: { params: Promise<{ id: string }> }) {
  const token = await gardenToken();
  if (!token) redirect('/garden/login');
  const recruitId = Number((await params).id);
  if (!Number.isInteger(recruitId) || recruitId < 1) notFound();

  let data: GardenRecruitImages;
  try {
    data = await fetchGardenRecruitImages(token, recruitId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect('/garden/login');
    if (e instanceof ApiError && e.status === 404) notFound(); // 自分の求人でなければ、存在しないのと同じ
    return (
      <main className="page">
        <p className="notice" role="alert">
          ただいま利用できません。しばらくしてから、もう一度お試しください
        </p>
      </main>
    );
  }
  const order = data.images.map((image) => image.id).join(',');

  return (
    <main className="page">
      <p>
        <Link href="/garden" className="text-link">
          ← 園の管理にもどる
        </Link>
      </p>
      <h1 className="garden-title">{data.category ?? '求人'}の画像</h1>
      <p className="garden-email">
        {data.is_displayed ? 'この求人は公開されています' : 'この求人は非表示です'}（画像は {data.images.length} / {data.max_images} 枚）。
        登録した画像は運営が承認するまで公開されません。ヒーロー（一番大きく出る画像）にできるのは、公開中の画像です。
      </p>

      <ul className="image-list">
        {data.images.map((image, index) => (
          <li key={image.id} className="image-item">
            {/* 承認前の画像もあるので、認証付きのプレビューを使う（公開 URL ではない） */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/garden/images/${image.id}/preview`} alt={image.alt} width={240} height={Math.round((240 * image.height) / image.width)} />
            <div className="image-meta">
              <p>
                <strong>{index + 1}.</strong> {image.is_hero ? <span className="image-badge">ヒーロー</span> : null}{' '}
                <span className={`image-status ${image.status}`}>{STATUS[image.status]}</span>
              </p>
              <p className="image-alt">{image.alt}</p>
              <div className="image-actions">
                <form action={moveImageAction}>
                  <input type="hidden" name="recruit_id" value={recruitId} />
                  <input type="hidden" name="order" value={order} />
                  <input type="hidden" name="index" value={index} />
                  <button type="submit" name="direction" value="up" className="small-button" disabled={index === 0}>
                    ↑ 前へ
                  </button>{' '}
                  <button type="submit" name="direction" value="down" className="small-button" disabled={index === data.images.length - 1}>
                    ↓ 後ろへ
                  </button>
                </form>
                <form action={setHeroAction}>
                  <input type="hidden" name="recruit_id" value={recruitId} />
                  <input type="hidden" name="image_id" value={image.id} />
                  <button type="submit" className="small-button" disabled={image.status !== 'approved' || image.is_hero}>
                    ヒーローにする
                  </button>
                </form>
                <form action={removeImageAction}>
                  <input type="hidden" name="recruit_id" value={recruitId} />
                  <input type="hidden" name="image_id" value={image.id} />
                  <button type="submit" className="small-button danger">
                    削除を依頼する
                  </button>
                </form>
              </div>
            </div>
          </li>
        ))}
      </ul>
      {data.images.length === 0 ? <p className="empty">まだ画像がありません。</p> : <p className="garden-email">削除を依頼した画像は、すぐには消えず、猶予のあとに運営が整理します。</p>}

      {data.images.length < data.max_images ? (
        <section aria-labelledby="upload-heading">
          <h2 id="upload-heading" className="garden-heading">
            画像を追加する
          </h2>
          <ImageUploadForm recruitId={recruitId} />
        </section>
      ) : null}
    </main>
  );
}
