# 開発

README の Quick start の続き。ローカルでの開発・テスト・ダミーデータ・CI の手順。

## 構成と版

| 場所 | 役割 | 版 |
|---|---|---|
| `backend/` | API（FastAPI + psycopg3。生の SQL） | Python 3.13 |
| `frontend/` | 画面（Next.js、TypeScript） | Node 24 |
| `db/` | 初期スキーマ（`schema.sql`）とマスタ（`seed_codes.sql`）。空のボリュームで初めて起動したときだけ流れる | Postgres 17 |
| `jobs/image-gen/` | 画像生成の Cloud Run Job（試作。[docs/image-gen-resources.md](image-gen-resources.md)） | Python 3.11 |
| `.devcontainer/` | 開発コンテナと、Docker のソケットプロキシ | |

版の基準は `.python-version` と `.node-version`。`scripts/check-versions.sh` が、Dockerfile・Compose・`engines`・CI と揃っているかを確かめる。
ポートは画面 3200、API 8200（ほかのローカルのサービスと同時に動かすため、固定）。

## テスト

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.in
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres .venv/bin/python -m pytest -q

cd frontend && npm ci && npm test && npm run build && npm run typecheck   # typecheck は build の後
```

`TEST_DATABASE_URL`（Postgres 17）が無いと、DB を使うテスト（ほぼ全部）は飛ばされる。飛ばされたまま通っても、検証したことにならない。
`backend/requirements.txt` は `requirements.in` から作った固定版で、直接編集しない。

## ダミーデータ

`seed` と `seed-images` は、開発・テスト専用。`DEMO_DATA=allow` が無いと実行を拒否する。本番の DB に向けない。

```bash
docker compose run --rm seed python -m app.seed_demo --reset            # ダミーデータだけ入れ直す
docker compose run --rm seed python -m app.seed_demo --extend           # 求人を 30 件構成（園 12・表示 26・非表示 4）に増やす
docker compose run --rm seed python -m app.seed_demo --reset --extend   # 入れ直して 30 件にする
```

`--extend` は、足りない分だけ足し、何度実行しても増えない。既存の求人・アカウントは変えない。引数なしの `seed` は 12 件。先に開発 DB のバックアップを取る（[docs/image-storage.md](image-storage.md)）。
園の会員登録の画面・API は無く、園のアカウントは `seed` で作る。

## マイグレーション

適用の前に、必ず DB のバックアップを取る（[docs/image-storage.md](image-storage.md)）。

```bash
docker compose run --rm migrate python -m app.migrate --status    # 読むだけ
docker compose run --rm migrate python -m app.migrate --dry-run   # 事前検査だけ
docker compose run --rm migrate                                   # 適用
```

## 画像の生成

`frontend/scripts/generate-images/`（Gemini の Batch API。課金される。手順は同じ場所の README）。生成した画像は `python -m app.images_cli register` で登録する。

## CI

[.github/workflows/ci.yml](../.github/workflows/ci.yml)。`main` への push と PR で、バックエンドのテスト（Postgres 17）、バックエンドのイメージのビルド、フロントエンドのテスト・ビルド・型検査、ワークフローの静的検査を行う。外部の API は呼ばず、デプロイは含まない。

## 秘密の検査

コミットの前後に、登録した語（実プロジェクト ID など）が入っていないかを `scripts/check-sensitive-terms.sh` で検査できる。語は Git の管理外の `.git/sensitive-terms` に置く（リポジトリには置かない）。
