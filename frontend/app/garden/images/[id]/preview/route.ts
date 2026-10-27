import { ApiError, fetchGardenImagePreview } from '../../../../../src/lib/api';
import { gardenToken } from '../../../../../src/lib/session';

export const dynamic = 'force-dynamic';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// 承認前の画像のプレビュー。ログインの印（HttpOnly の Cookie）は画面のサーバーだけが読めるので、ここで API へ中継する。
// 認証と所有権の確認は API が行い、通らなければ 404（他の園の画像が存在するかも分からない）。
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await params;
  const token = await gardenToken();
  if (!token) return new Response(null, { status: 401 });
  if (!UUID.test(id)) return new Response(null, { status: 404 });
  try {
    const upstream = await fetchGardenImagePreview(token, id);
    return new Response(upstream.body, {
      headers: {
        'Content-Type': upstream.headers.get('content-type') ?? 'application/octet-stream',
        'Cache-Control': 'private, no-store',
        'X-Content-Type-Options': 'nosniff',
      },
    });
  } catch (e) {
    return new Response(null, { status: e instanceof ApiError && e.status === 401 ? 401 : 404 });
  }
}
