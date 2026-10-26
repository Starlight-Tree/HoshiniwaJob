# 星庭ジョブ（hoshiniwa-job）

架空の宇宙の植物園・ガーデンの求人サイト（運営は架空の「星庭ワークス」）。月面・軌道都市・惑星ザーハード、通貨「ノクト」など、すべて架空。データはすべてダミー。

FastAPI + psycopg3（`backend/`）/ Next.js + TypeScript（`frontend/`）/ Postgres 17（`db/`）/ Docker Compose。

## 起動

ホストのターミナルで、このフォルダーで実行する。

```bash
docker compose up --build   # 初回。2 回目からは docker compose up
```

- 画面: <http://localhost:3200>（初回は `npm install` で 1〜2 分）
- API の文書: <http://localhost:8200/docs>
- 止める: `docker compose down`。DB ごと消すなら `docker compose down -v`

ダミーのアカウント（ローカル専用）: 利用者 `hoshiniwa-user@example.com`、園 `hoshiniwa-garden@example.com` と `hoshiniwa-garden2@example.com`、パスワードは `star-garden-demo`。
ダミーデータだけ入れ直す: `docker compose run --rm seed python -m app.seed_demo --reset`

## 機能

- **求人検索**: 条件（雇用形態・エリア・乗り場・職種）は URL に持つ。同じ種類の中は OR、種類の間は AND。条件ごとの件数、チップでの解除。
- **利用者の会員登録・ログイン・ログアウト**（`/register`、`/login`）: パスワードは argon2。ログインの印は HttpOnly の Cookie（`hj_session`）。https で公開するときは `SESSION_COOKIE_SECURE=true`。
- **園のログイン・ログアウト**（<http://localhost:3200/garden/login>）: 利用者とは別のアカウント・別のセッション・別の Cookie（`hj_garden_session`）。ダッシュボード（`/garden`）には、自分の法人の求人の件数だけが出る。園の会員登録の画面・API は無く、アカウントは `seed` で作る。

## 開発とテスト

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.in
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres .venv/bin/python -m pytest -q   # 未設定なら DB のテストは飛ばす

cd frontend && npm install && npm test && npm run build && npm run typecheck   # typecheck は build の後
```

`backend/requirements.txt` は `requirements.in` から作った固定版。直接編集しない。

## これから

パスワード再設定、応募、園の管理画面、CSV・PDF 出力、メール送信、画像、お知らせ記事。

## ライセンス

[LICENSE](LICENSE) を参照してください。
