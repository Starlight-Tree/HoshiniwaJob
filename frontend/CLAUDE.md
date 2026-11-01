# frontend/（画面）

全体の方針・禁止事項は、ルートの [CLAUDE.md](../CLAUDE.md)。画像の仕組みは [docs/image-storage.md](../docs/image-storage.md)。画面の調査の記録は [docs/ux-research.md](../docs/ux-research.md)。

Next.js 16（App Router）、React 19、TypeScript 7、Vitest 5。Node 24（`engines` は `^22.12.0 || ^24.0.0 || >=26.0.0`。基準は 24）。

## 構成

| 場所 | 役割 |
|---|---|
| `app/(site)/` | 公開側。求人検索（`page.tsx`）と求人詳細（`recruits/[id]`） |
| `app/(auth)/` | 利用者の登録・ログイン |
| `app/garden/` | 園。ログイン、ダッシュボード、求人ごとの画像の管理（`recruits/[id]/images`） |
| `src/actions/` | サーバーアクション（`'use server'`）。フォームの受け口で、検証してから API を呼ぶ |
| `src/lib/` | `api.ts`（API の呼び出し。サーバー側だけ）、`session.ts`（Cookie）、`search.ts`（URL の条件）、`validation.ts` ほか |
| `src/components/` | 部品。テストは同じ場所の `*.test.tsx` |
| `public/images/generated/` | 生成済みの画像。Git 管理。`seed-images` の元ファイルでもある |
| `scripts/generate-images/` | 画像の一括生成（Gemini の Batch API。課金される）。手順は同じ場所の README |

## 守ること

- **API はサーバー側（サーバーアクション・Server Component）から呼ぶ。** ブラウザーは API を直接呼ばないので、CORS に頼らない。ログインの印のトークンは HttpOnly の Cookie に入れ、ブラウザーの JavaScript に渡さない。
- **`NEXT_PUBLIC_*` に秘密を入れない。** 今は 1 つも使っていない。バンドルに埋め込まれ、誰でも読める。環境変数は `API_BASE_URL` `IMAGE_PUBLIC_BASE_URL` `SESSION_COOKIE_SECURE` だけ。
- **`IMAGE_PUBLIC_BASE_URL` は API と同じ値にする。** `next.config.ts` が、外部画像の許可（`remotePatterns`）を、その配信元の `images/` だけに限る。広げない。
- **`next.config.ts` の `agentRules: false` を外さない**（`next dev` が `AGENTS.md` を自動で作るのを止めている）。`logging.serverFunctions: false` も、メールなどを端末に出さないための設定。
- **画面の検証は API の検証の代わりにならない。** `garden-images.ts` の形式・容量の検査は手前の確認で、本当の検査は API。
- **`public/images/generated/recruits/` の画像を差し替える・生成し直すときは、`backend/app/demo_images.json` の `sha256` も同じ変更で更新する。** 一致しない画像は `seed-images` が使わない。
- 画像の一括生成は課金される。実行の前に、枚数と概算費用を示して承認を得る（`--dry-run` は課金なし）。キー（`GEMINI_API_KEY`）は `scripts/generate-images/.env`（Git 管理外）か環境変数で渡し、表示しない。
- 画面を変えたら、前例（`docs/ux-research.md`）にならって Playwright で確かめる。基準は幅 1280px。390px は横スクロールが出ないことの確認だけ。

## テストと検査

```bash
cd frontend
npm ci
npm test            # vitest（jsdom）。テストは src/ に同居（*.test.ts / *.test.tsx）
npm run build
npm run typecheck   # build の後（.next/types を使う）
```

- `vitest.config.ts`: `environment: 'jsdom'`、`restoreMocks: true`、`src/test/setup.ts`。実 API・ネットワークを呼ばない。`fetch` は `vi.spyOn(globalThis, 'fetch')`、`next/headers` と `next/navigation` は `vi.mock` で差し替える。
- `node_modules` と `.next` はホストと Compose のコンテナで分けている（ネイティブの依存が OS ごとに違うため）。開発コンテナからこのフォルダーで `npm ci` すると、ホストの `node_modules` を上書きしうる。別の場所にコピーして確かめる。
- lint（eslint など）は未導入。
