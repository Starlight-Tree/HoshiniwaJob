import type {
  Facets,
  Garden,
  GardenRecruitImages,
  GardenRecruitItem,
  GardenSession,
  GardenSummary,
  Master,
  RecruitDetail,
  RecruitPage,
  RecruitSummary,
  User,
} from './types';
import { KINDS, type Selection } from './search';

// 画面のサーバー側（Next.js）から API を呼ぶ。ブラウザーは API を直接呼ばないので、CORS は要らない。
// Docker の Compose では http://api:8000、開発コンテナや素の起動では http://localhost:8000。
const BASE = (process.env.API_BASE_URL ?? 'http://localhost:8000').replace(/\/+$/, '');

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

type CallOptions = { method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'; body?: unknown; token?: string; raw?: { bytes: ArrayBuffer; contentType: string } };

async function call(path: string, { method = 'GET', body, token, raw }: CallOptions = {}): Promise<Response> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (raw) headers['Content-Type'] = raw.contentType;
  try {
    return await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: raw ? raw.bytes : body === undefined ? undefined : JSON.stringify(body),
      cache: 'no-store',
    });
  } catch {
    throw new ApiError(0, 'API に接続できません');
  }
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new ApiError(res.status, `API がエラーを返しました（${res.status}）`);
  return (await res.json()) as T;
}

const get = async <T>(path: string, token?: string): Promise<T> => json<T>(await call(path, { token }));

function conditions(sel: Selection): URLSearchParams {
  const q = new URLSearchParams();
  for (const kind of KINDS) for (const code of sel[kind]) q.append(kind, String(code));
  if (sel.q) q.set('q', sel.q);
  return q;
}

export const fetchMaster = () => get<Master>('/api/master');

export function fetchFacets(sel: Selection): Promise<Facets> {
  return get<Facets>(`/api/facets?${conditions(sel)}`);
}

export function fetchRecruits(sel: Selection, perPage = 10): Promise<RecruitPage> {
  const q = conditions(sel);
  q.set('page', String(sel.page));
  q.set('per_page', String(perPage));
  return get<RecruitPage>(`/api/recruits?${q}`);
}

export const fetchRecruit = (id: number) => get<RecruitDetail>(`/api/recruits/${id}`);

/** 関連する求人（公開 API。docs/recommendation.md）。自分は含まれない。limit は API が 1〜12 に限る。存在しない・表示中でない求人は 404。 */
export const fetchRelatedRecruits = (id: number, limit = 4) => get<RecruitSummary[]>(`/api/recruits/${id}/related?limit=${limit}`);

// 求職者の API。ログインは Better Auth（lib/auth.ts）。ここへ渡すトークンは、そこが出す JWT（session.ts の userToken）。
export const fetchMe = (token: string) => get<User>('/api/auth/me', token);

/** 閲覧の記録（求職者の Bearer。成功は 204 で本文なし。同じ求人を 30 分以内にもう一度送っても 204 で、足されない）。無いトークンは 401、存在しない・表示中でない求人は 404。 */
export async function recordRecruitView(token: string, id: number): Promise<void> {
  const res = await call(`/api/recruits/${id}/view`, { method: 'POST', token });
  if (!res.ok) throw new ApiError(res.status, `API がエラーを返しました（${res.status}）`);
}

/** あなたへのおすすめ（求職者の Bearer）。まだ見ていない求人から選ぶ。閲覧の履歴が無ければ []。limit は API が 1〜12 に限る。 */
export const fetchRecommendations = (token: string, limit = 6) => get<RecruitSummary[]>(`/api/recommendations?limit=${limit}`, token);

/** 表示名（ニックネーム）の変更。変えられるのは、トークンの持ち主本人だけ。 */
export async function updateNameRequest(token: string, input: { display_name: string }): Promise<User> {
  return json<User>(await call('/api/auth/me', { method: 'PATCH', token, body: input }));
}

// 園の認証。利用者とは別の API・別のトークン（Cookie に入れるのは session.ts）。
export async function gardenLoginRequest(email: string, password: string): Promise<GardenSession> {
  return json<GardenSession>(await call('/api/garden/auth/login', { method: 'POST', body: { email, password } }));
}

export const fetchGardenMe = (token: string) => get<Garden>('/api/garden/auth/me', token);

export const fetchGardenSummary = (token: string) => get<GardenSummary>('/api/garden/summary', token);

export async function gardenLogoutRequest(token: string): Promise<void> {
  const res = await call('/api/garden/auth/logout', { method: 'POST', token });
  if (!res.ok) throw new ApiError(res.status, `API がエラーを返しました（${res.status}）`);
}

// 園の画像管理。トークンは画面のサーバーだけが持ち、所有権の確認は API 側で行う（画面では判断しない）。
export const fetchGardenRecruits = (token: string) => get<GardenRecruitItem[]>('/api/garden/recruits', token);

export const fetchGardenRecruitImages = (token: string, recruitId: number) =>
  get<GardenRecruitImages>(`/api/garden/recruits/${recruitId}/images`, token);

export async function uploadGardenImage(token: string, recruitId: number, file: { bytes: ArrayBuffer; contentType: string }, alt: string): Promise<void> {
  const res = await call(`/api/garden/recruits/${recruitId}/images?alt=${encodeURIComponent(alt)}`, { method: 'POST', token, raw: file });
  if (!res.ok) throw new ApiError(res.status, await detailOf(res));
}

export async function reorderGardenImages(token: string, recruitId: number, imageIds: string[]): Promise<void> {
  await json<GardenRecruitImages>(await call(`/api/garden/recruits/${recruitId}/images/order`, { method: 'PUT', token, body: { image_ids: imageIds } }));
}

export async function setGardenHeroImage(token: string, recruitId: number, imageId: string): Promise<void> {
  await json<GardenRecruitImages>(await call(`/api/garden/recruits/${recruitId}/images/hero`, { method: 'PUT', token, body: { image_id: imageId } }));
}

export async function removeGardenImage(token: string, recruitId: number, imageId: string): Promise<void> {
  const res = await call(`/api/garden/recruits/${recruitId}/images/${imageId}`, { method: 'DELETE', token });
  if (!res.ok) throw new ApiError(res.status, `API がエラーを返しました（${res.status}）`);
}

// 登録の拒否理由（形式・容量・寸法）は、API の固定の説明をそのまま画面に出してよい（内部の情報を含まない）
async function detailOf(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body.detail === 'string' ? body.detail : `API がエラーを返しました（${res.status}）`;
  } catch {
    return `API がエラーを返しました（${res.status}）`;
  }
}
