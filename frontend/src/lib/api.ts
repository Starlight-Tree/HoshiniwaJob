import type { Facets, Master, RecruitDetail, RecruitPage, Session, User } from './types';
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

type CallOptions = { method?: 'GET' | 'POST'; body?: unknown; token?: string };

async function call(path: string, { method = 'GET', body, token }: CallOptions = {}): Promise<Response> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  try {
    return await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
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

// 求職者の認証。トークンは画面のサーバーだけが持つ（Cookie に入れるのは session.ts）。
export async function loginRequest(email: string, password: string): Promise<Session> {
  return json<Session>(await call('/api/auth/login', { method: 'POST', body: { email, password } }));
}

export type RegisterInput = { last_name: string; first_name: string; email: string; password: string };

export async function registerRequest(input: RegisterInput): Promise<Session> {
  return json<Session>(await call('/api/auth/register', { method: 'POST', body: input }));
}

export const fetchMe = (token: string) => get<User>('/api/auth/me', token);

export async function logoutRequest(token: string): Promise<void> {
  const res = await call('/api/auth/logout', { method: 'POST', token });
  if (!res.ok) throw new ApiError(res.status, `API がエラーを返しました（${res.status}）`);
}
