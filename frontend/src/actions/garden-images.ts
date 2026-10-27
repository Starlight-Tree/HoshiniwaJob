'use server';

import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';
import { ApiError, removeGardenImage, reorderGardenImages, setGardenHeroImage, uploadGardenImage } from '../lib/api';
import { gardenToken } from '../lib/session';

export type ImageFormState = { error?: string; ok?: string };

const ALLOWED = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_BYTES = 5 * 1024 * 1024; // API の既定の上限と同じ（本当の検査は API）
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const text = (data: FormData, key: string) => String(data.get(key) ?? '');
const back = (recruitId: number) => `/garden/recruits/${recruitId}/images`;

async function requireToken(): Promise<string> {
  const token = await gardenToken();
  if (!token) redirect('/garden/login');
  return token;
}

function recruitIdOf(data: FormData): number {
  const id = Number(text(data, 'recruit_id'));
  if (!Number.isInteger(id) || id < 1) redirect('/garden');
  return id;
}

// 失敗は固定の文にする。API が返した理由（形式・容量・寸法）は、内部の情報を含まない固定の説明なので出してよい
function messageFor(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 401) redirect('/garden/login');
    if (e.status === 404) return '対象の求人または画像が見つかりません';
    if ([409, 413, 415, 422].includes(e.status) && e.message && !e.message.startsWith('API がエラー')) return e.message;
  }
  return 'ただいま利用できません。しばらくしてから、もう一度お試しください';
}

export async function uploadImageAction(_prev: ImageFormState, data: FormData): Promise<ImageFormState> {
  const token = await requireToken();
  const recruitId = recruitIdOf(data);
  const alt = text(data, 'alt').trim();
  const file = data.get('file');
  if (!(file instanceof File) || file.size === 0) return { error: '画像のファイルを選んでください' };
  if (alt.length < 1 || alt.length > 300) return { error: '代替テキストは 1〜300 文字で入れてください' };
  if (!ALLOWED.includes(file.type)) return { error: 'JPEG・PNG・WebP の画像だけ登録できます' };
  if (file.size > MAX_BYTES) return { error: '画像は 5MB 以下にしてください' };
  try {
    await uploadGardenImage(token, recruitId, { bytes: await file.arrayBuffer(), contentType: file.type }, alt);
  } catch (e) {
    return { error: messageFor(e) };
  }
  revalidatePath(back(recruitId));
  return { ok: '画像を登録しました。運営の承認が済むと公開されます。' };
}

export async function moveImageAction(data: FormData): Promise<void> {
  const token = await requireToken();
  const recruitId = recruitIdOf(data);
  const ids = text(data, 'order').split(',').filter(Boolean);
  const index = Number(text(data, 'index'));
  const to = index + (text(data, 'direction') === 'up' ? -1 : 1);
  if (ids.some((id) => !UUID.test(id)) || !Number.isInteger(index) || index < 0 || to < 0 || to >= ids.length) redirect(back(recruitId));
  [ids[index], ids[to]] = [ids[to]!, ids[index]!];
  try {
    await reorderGardenImages(token, recruitId, ids);
  } catch (e) {
    messageFor(e); // 401 のときだけログインへ戻す。ほかの失敗は、画面を開き直して今の状態を見てもらう
  }
  revalidatePath(back(recruitId));
  redirect(back(recruitId));
}

export async function setHeroAction(data: FormData): Promise<void> {
  const token = await requireToken();
  const recruitId = recruitIdOf(data);
  const imageId = text(data, 'image_id');
  if (UUID.test(imageId)) {
    try {
      await setGardenHeroImage(token, recruitId, imageId);
    } catch (e) {
      messageFor(e);
    }
  }
  revalidatePath(back(recruitId));
  redirect(back(recruitId));
}

export async function removeImageAction(data: FormData): Promise<void> {
  const token = await requireToken();
  const recruitId = recruitIdOf(data);
  const imageId = text(data, 'image_id');
  if (UUID.test(imageId)) {
    try {
      await removeGardenImage(token, recruitId, imageId);
    } catch (e) {
      messageFor(e);
    }
  }
  revalidatePath(back(recruitId));
  redirect(back(recruitId));
}
