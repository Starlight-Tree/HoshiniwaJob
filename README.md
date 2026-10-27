# 星庭ジョブ（hoshiniwa-job）

架空の宇宙の植物園・ガーデンの求人サイト（運営は架空の「星庭ワークス」）。月面・軌道都市・惑星ザーハード、通貨「ノクト」など、すべて架空。データはすべてダミー。

FastAPI + psycopg3（`backend/`）/ Next.js + TypeScript（`frontend/`）/ Postgres 17（`db/`）/ Docker Compose。

## 起動

ホストのターミナルで、このフォルダーで実行する。

```bash
docker compose up -d --build   # 起動。マイグレーションもダミーデータも流さない
```

**初めての環境（空の DB）**は、先にこの順で 1 回ずつ実行する（`migrate` `seed` `seed-images` は、`up` では起動しない「道具」）。`seed` と `seed-images` は開発・テスト専用で、`DEMO_DATA=allow` が無いと実行を拒否する（Compose の定義が渡す。本番の環境には渡さない）。

```bash
docker compose up -d db
docker compose run --rm migrate       # マイグレーション（本番でも、デプロイの作業として明示的に実行するのはこれだけ）
docker compose run --rm seed          # ダミーの求人・アカウント（開発・テスト専用）
docker compose run --rm seed-images   # ダミーの画像（開発・テスト専用。何度実行しても増えない）
docker compose up -d --build
```

- 画面: <http://localhost:3200>（初回は `npm install` で 1〜2 分）
- API の文書: <http://localhost:8200/docs>
- 止める: `docker compose down`。DB ごと消すなら `docker compose down -v`
- 通常の起動は、画像の元ファイル（`frontend/public/images/generated/recruits/`）やダミーデータに依存しない。画像の詳細は [docs/image-storage.md](docs/image-storage.md)

ダミーのアカウント（ローカル専用）: 利用者 `hoshiniwa-user@example.com`、園 `hoshiniwa-garden@example.com` と `hoshiniwa-garden2@example.com`、パスワードは `star-garden-demo`。
ダミーデータだけ入れ直す: `docker compose run --rm seed python -m app.seed_demo --reset`

## 機能

- **求人検索**: 条件（雇用形態・エリア・乗り場・職種）は URL に持つ。同じ種類の中は OR、種類の間は AND。条件ごとの件数、チップでの解除。
- **利用者の会員登録・ログイン・ログアウト**（`/register`、`/login`）: パスワードは argon2。ログインの印は HttpOnly の Cookie（`hj_session`）。https で公開するときは `SESSION_COOKIE_SECURE=true`。
- **園のログイン・ログアウト**（<http://localhost:3200/garden/login>）: 利用者とは別のアカウント・別のセッション・別の Cookie（`hj_garden_session`）。ダッシュボード（`/garden`）には、自分の法人の求人の件数だけが出る。園の会員登録の画面・API は無く、アカウントは `seed`（開発・テスト専用）で作る。

- **求人・法人の画像**: 画像の本体はストレージ（開発は Compose のボリューム、本番は S3 互換の Cloudflare R2 を想定。バケットは 1 つ）、求人との対応は DB。園は `/garden` から、自分の求人の画像をドラッグ＆ドロップで追加（保存前にプレビュー）・並べ替え・ヒーロー指定・削除ができる。追加した画像はすぐ公開され、削除もその場で行われる。公開後の取り下げだけ、運営が行う（`python -m app.images_cli reject`）。設定・登録・移行・バックアップと復旧・R2 の手順は [docs/image-storage.md](docs/image-storage.md)。

## 開発とテスト

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.in
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres .venv/bin/python -m pytest -q   # 未設定なら DB のテストは飛ばす

cd frontend && npm install && npm test && npm run build && npm run typecheck   # typecheck は build の後
```

既存の DB のマイグレーション（適用前に必ずバックアップ。[docs/image-storage.md](docs/image-storage.md)）:

```bash
docker compose run --rm migrate python -m app.migrate --status    # 読むだけ
docker compose run --rm migrate python -m app.migrate --dry-run   # 事前検査だけ
docker compose run --rm migrate                                   # 適用
```

画像の生成（Gemini の Batch API）は `frontend/scripts/generate-images/`。生成した画像は `python -m app.images_cli register` で登録する。

`backend/requirements.txt` は `requirements.in` から作った固定版。直接編集しない。

## これから

パスワード再設定、応募、園の管理画面（画像以外）、CSV・PDF 出力、メール送信、法人画像の表示、お知らせ記事。

## ライセンス

[LICENSE](LICENSE) を参照してください。
