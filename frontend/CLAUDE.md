# frontend/（画面）

全体の方針・禁止事項は、ルートの [CLAUDE.md](../CLAUDE.md)。画像の仕組みは [docs/image-storage.md](../docs/image-storage.md)。画面の調査の記録は [docs/ux-research.md](../docs/ux-research.md)。

Next.js 16（App Router）、React 19、TypeScript 7、Vitest 5。Node 24（`engines` は `^22.12.0 || ^24.0.0 || >=26.0.0`。基準は 24）。

## 構成

| 場所 | 役割 |
|---|---|
| `app/(site)/` | 公開側。求人検索（`page.tsx`。しぼり込み `FilterForm` は、DocuNavi の資料一覧と同じ、上の横並びのチップ。押すと複数選べる一覧が開く）と求人詳細（`recruits/[id]`）。左のサイドパネル（`AppSidebar`。DocuNavi と同じく、開いた表示と細い帯をボタンで切り替える。はじめは開いた状態で保存しない。開閉できるのは DocuNavi と同じ 1024px 以上。1023px 以下は上の横帯）と、アカウントのメニュー（`AccountMenu`。テーマの切り替えもここ） |
| `app/(auth)/` | 利用者のログイン（Google だけ。DocuNavi と同じ。はじめてのログインで登録される）。「Google でログイン」は、サーバーアクション（`googleLoginAction`）のフォーム。`/register` は `/login` へ移すだけ。サイドパネルは出さず、上の帯に「← 求人を探す」とテーマの切り替えだけ |
| `app/api/auth/[...all]/` | Better Auth の入口（Google への行き来・Cookie・JWKS `/api/auth/jwks`）。Next.js の公式の組み込み方。設定が足りないときは 503。設定と DB 接続は `src/lib/auth.ts`（利用者の表は `auth_` 付き。`backend/app/migrations/0004_better_auth.sql`）。API へは、`src/lib/session.ts` の `userToken()` が `auth.api.getToken` で取る短命の JWT を、Bearer で渡す |
| `app/garden/` | 園。ログイン、ダッシュボード、求人ごとの画像の管理（`recruits/[id]/images`）。サイドパネルは `(site)` と同じ部品（ログイン前は行き先を出さず、アカウントのメニューはテーマだけ） |
| `src/actions/` | サーバーアクション（`'use server'`）。フォームの受け口で、検証してから API を呼ぶ |
| `src/lib/` | `api.ts`（API の呼び出し。サーバー側だけ）、`session.ts`（Cookie）、`search.ts`（URL の条件）、`validation.ts` ほか |
| `src/components/` | 部品。テストは同じ場所の `*.test.tsx` |
| `public/images/generated/` | 生成済みの画像。Git 管理。`seed-images` の元ファイルでもある |
| `scripts/generate-images/` | 画像の一括生成（Gemini の Batch API。課金される）。手順は同じ場所の README |

## 守ること

- **API はサーバー側（サーバーアクション・Server Component）から呼ぶ。** ブラウザーは API を直接呼ばないので、CORS に頼らない。ログインの印は Better Auth の HttpOnly の Cookie で、ブラウザーの JavaScript に渡さない。API へ渡すのは、そこから取る 15 分の JWT。園のログインは別（`hj_garden_session`。トークンは HttpOnly の Cookie）。
- **`NEXT_PUBLIC_*` に秘密を入れない。** 今は 1 つも使っていない。バンドルに埋め込まれ、誰でも読める。環境変数は `API_BASE_URL` `IMAGE_PUBLIC_BASE_URL` `SESSION_COOKIE_SECURE` と、ログイン（Better Auth。画面のサーバーだけが読む）の `BETTER_AUTH_URL` `BETTER_AUTH_SECRET` `GOOGLE_CLIENT_ID` `GOOGLE_CLIENT_SECRET` `DATABASE_URL`（api・migrate と同じ資格情報。表ごとの権限分けはしていないので、`auth_` の表だけを使うのは、コードの上の約束）。**どれも `NEXT_PUBLIC_` を付けない。画面のコンテナが DB を使うのは、ログインのためだけで、求人などのデータは API 経由で読む。**
  `BETTER_AUTH_SECRET` は、決めたら変えない（理由と、変えたときの直し方はルートの `CLAUDE.md`）。migrate の前に画面を使うと、画面を再起動するまで直らない。握りつぶす例外は `lib/auth-log.ts` でログに 1 行出す。Cookie 名の接頭辞は `hoshiniwajob`（既定の `better-auth` だと、同じ localhost の DocuNavi と取り合う）。
- **`IMAGE_PUBLIC_BASE_URL` は API と同じ値にする。** `next.config.ts` が、外部画像の許可（`remotePatterns`）を、その配信元の `images/` だけに限る。広げない。
- **`next.config.ts` の `agentRules: false` を外さない**（`next dev` が `AGENTS.md` を自動で作るのを止めている）。`logging.serverFunctions: false` も、メールなどを端末に出さないための設定。
- **テーマ（ライト / ダーク / システム）は `src/lib/theme.ts` に集約する。** 色は `app/globals.css` の変数だけで決め、本体に色（`#xxxxxx`・`rgba`）を直書きしない（`theme.test.ts` が落とす）。ダークの値は、OS 追従（`@media`）と `:root[data-theme='dark']` の 2 か所に同じ内容で書く（これも `theme.test.ts` が一致を確かめる）。新しい色の変数は、ライトとダークの両方に足し、文字は WCAG AA（4.5:1）を満たす。保存先のキーは `hoshiniwajob-theme`。描画前のスクリプト（`app/layout.tsx`）が同じキーを読む。
- **画面の検証は API の検証の代わりにならない。** `garden-images.ts` の形式・容量の検査は手前の確認で、本当の検査は API。
- **`public/images/generated/recruits/` の画像を差し替える・生成し直すときは、`backend/app/demo_images.json` の `sha256` も同じ変更で更新する。** 一致しない画像は `seed-images` が使わない。
- 画像の一括生成は課金される。実行の前に、枚数と概算費用を示して承認を得る（`--dry-run` は課金なし）。キー（`GEMINI_API_KEY`）は `scripts/generate-images/.env`（Git 管理外）か環境変数で渡し、表示しない。
- 画面を変えたら、前例（`docs/ux-research.md`）にならって Playwright で確かめる。基準は幅 1280px。390px は横スクロールが出ないことの確認だけ。

## テストと検査

```bash
# ホストで実行する（開発コンテナの作業ツリーでは npm ci しない。下の注意）
cd frontend
npm ci
npm test            # vitest（jsdom）。テストは src/ に同居（*.test.ts / *.test.tsx）
npm run build
npm run typecheck   # build の後（.next/types を使う）
```

- `vitest.config.ts`: `environment: 'jsdom'`、`restoreMocks: true`、`src/test/setup.ts`。実 API・ネットワークを呼ばない。`fetch` は `vi.spyOn(globalThis, 'fetch')`、`next/headers` と `next/navigation` は `vi.mock` で差し替える。
- `node_modules` と `.next` はホストと Compose のコンテナで分けている（ネイティブの依存が OS ごとに違うため）。開発コンテナからこのフォルダーで `npm ci` すると、ホストの `node_modules` を上書きしうる。別の場所にコピーして確かめる。
- lint（eslint など）は未導入。
