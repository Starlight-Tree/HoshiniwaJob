import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const store = new Map<string, { value: string }>();
vi.mock('next/headers', () => ({
  cookies: async () => ({ get: (k: string) => (store.has(k) ? { name: k, value: store.get(k)!.value } : undefined) }),
}));
class Redirected extends Error {
  constructor(readonly to: string) {
    super(to);
  }
}
vi.mock('next/navigation', () => ({
  redirect: (to: string) => {
    throw new Redirected(to);
  },
}));
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));

const { uploadImageAction, moveImageAction, setHeroAction, removeImageAction } = await import('./garden-images');

const A = '11111111-1111-4111-8111-111111111111';
const B = '22222222-2222-4222-8222-222222222222';
const C = '33333333-3333-4333-8333-333333333333';

const form = (fields: Record<string, string | File>) => {
  const f = new FormData();
  for (const [k, v] of Object.entries(fields)) f.set(k, v);
  return f;
};
const jpeg = (bytes = 10, type = 'image/jpeg') => new File([new Uint8Array(bytes)], 'a.jpg', { type });
const reply = (status: number, body?: unknown) =>
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(body === undefined ? null : JSON.stringify(body), { status }));

beforeEach(() => {
  store.clear();
  store.set('hj_garden_session', { value: 'garden-tok' });
});
afterEach(() => vi.restoreAllMocks());

describe('uploadImageAction', () => {
  it('ログインしていなければ、API を呼ばずにログインへ移す', async () => {
    store.clear();
    const fetchMock = reply(201, {});
    await expect(uploadImageAction({}, form({ recruit_id: '1', alt: 'x', file: jpeg() }))).rejects.toMatchObject({ to: '/garden/login' });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    ['ファイル未選択', { recruit_id: '1', alt: 'x' }, '画像のファイルを選んでください'],
    ['代替テキストなし', { recruit_id: '1', alt: ' ', file: jpeg() }, '代替テキストは 1〜300 文字で入れてください'],
    ['GIF', { recruit_id: '1', alt: 'x', file: jpeg(10, 'image/gif') }, 'JPEG・PNG・WebP の画像だけ登録できます'],
    ['容量超過', { recruit_id: '1', alt: 'x', file: jpeg(5 * 1024 * 1024 + 1) }, '画像は 5MB 以下にしてください'],
  ])('%s は API を呼ばずに断る', async (_name, fields, message) => {
    const fetchMock = reply(201, {});
    expect(await uploadImageAction({}, form(fields as Record<string, string | File>))).toEqual({ error: message });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('成功したら、画像そのものを Content-Type 付きで API へ送る（トークンは Authorization だけ）', async () => {
    const fetchMock = reply(201, {});
    const state = await uploadImageAction({}, form({ recruit_id: '7', alt: '温室の画像', file: jpeg(32) }));
    expect(state.ok).toBe('画像を公開しました。');
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain('/api/garden/recruits/7/images?alt=' + encodeURIComponent('温室の画像'));
    expect(init?.method).toBe('POST');
    expect(init?.headers).toMatchObject({ Authorization: 'Bearer garden-tok', 'Content-Type': 'image/jpeg' });
    expect((init?.body as ArrayBuffer).byteLength).toBe(32);
  });

  it('API の拒否理由（固定の説明）は出し、想定外の失敗は固定の文にする。404 は見つからない旨', async () => {
    reply(422, { detail: '画像として読み込めません（形式が違うか、壊れています）' });
    expect((await uploadImageAction({}, form({ recruit_id: '1', alt: 'x', file: jpeg() }))).error).toContain('画像として読み込めません');
    reply(500, { detail: 'Traceback /app/secret.py' });
    expect((await uploadImageAction({}, form({ recruit_id: '1', alt: 'x', file: jpeg() }))).error).toBe('ただいま利用できません。しばらくしてから、もう一度お試しください');
    reply(404, { detail: '求人が見つかりません' });
    expect((await uploadImageAction({}, form({ recruit_id: '3', alt: 'x', file: jpeg() }))).error).toBe('対象の求人または画像が見つかりません');
  });
});

describe('moveImageAction', () => {
  it('隣と入れ替えた並びを PUT し、同じ画面へ戻る', async () => {
    const fetchMock = reply(200, { recruit_id: 1, images: [] });
    await expect(moveImageAction(form({ recruit_id: '1', order: `${A},${B},${C}`, index: '1', direction: 'up' }))).rejects.toMatchObject({ to: '/garden/recruits/1/images' });
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain('/api/garden/recruits/1/images/order');
    expect(init?.method).toBe('PUT');
    expect(JSON.parse(String(init?.body))).toEqual({ image_ids: [B, A, C] });
  });

  it('端を越える移動や、UUID でない値は API を呼ばない', async () => {
    const fetchMock = reply(200, {});
    await expect(moveImageAction(form({ recruit_id: '1', order: `${A},${B}`, index: '0', direction: 'up' }))).rejects.toBeInstanceOf(Redirected);
    await expect(moveImageAction(form({ recruit_id: '1', order: 'x,y', index: '0', direction: 'down' }))).rejects.toBeInstanceOf(Redirected);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('setHeroAction / removeImageAction', () => {
  it('ヒーローの指定と削除を API へ送る（所有権の判断は API）', async () => {
    const fetchMock = reply(200, {});
    await expect(setHeroAction(form({ recruit_id: '2', image_id: A }))).rejects.toMatchObject({ to: '/garden/recruits/2/images' });
    expect(fetchMock.mock.calls[0]![1]?.method).toBe('PUT');
    expect(JSON.parse(String(fetchMock.mock.calls[0]![1]?.body))).toEqual({ image_id: A });
    fetchMock.mockClear();
    await expect(removeImageAction(form({ recruit_id: '2', image_id: A }))).rejects.toMatchObject({ to: '/garden/recruits/2/images' });
    expect(String(fetchMock.mock.calls[0]![0])).toContain(`/api/garden/recruits/2/images/${A}`);
    expect(fetchMock.mock.calls[0]![1]?.method).toBe('DELETE');
  });

  it('401 ならログインへ移す', async () => {
    reply(401, {});
    await expect(setHeroAction(form({ recruit_id: '2', image_id: A }))).rejects.toMatchObject({ to: '/garden/login' });
  });
});
