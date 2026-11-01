# CLAUDE.md

星庭ジョブ（hoshiniwa-job）。架空の宇宙の植物園・ガーデンの求人サイト（運営は架空の「星庭ワークス」）。データはすべてダミー。
FastAPI + psycopg3（`backend/`）、Next.js + TypeScript（`frontend/`）、Postgres 17（`db/`）、Docker Compose。入口は [README.md](README.md)、
画像・マイグレーション・バックアップ・R2 の詳細は [docs/image-storage.md](docs/image-storage.md)、画面の調査は [docs/ux-research.md](docs/ux-research.md)。
**Vertex AI の画像生成ジョブ（デプロイ済みの設定・成功した実行・モデル）の正本は [docs/image-gen-resources.md](docs/image-gen-resources.md)。** 会話の履歴やログを探す前に、これを読む。
領域ごとの規約は `backend/` `frontend/` `jobs/image-gen/` `.devcontainer/` の各 `CLAUDE.md`、パス別の規則は `.claude/rules/`。

## よく使うコマンド

| 目的 | コマンド |
|---|---|
| 起動（ホストで） | `docker compose up -d --build`。画面 <http://localhost:3200>、API <http://localhost:8200/docs>。マイグレーションもダミーデータも流さない |
| 初めての環境（空の DB） | `docker compose up -d db` → `run --rm migrate` → `run --rm seed` → `run --rm seed-images` → `up -d --build`（README の「起動」） |
| バックエンドのテスト | `cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.in`、`TEST_DATABASE_URL=<Postgres の URL> .venv/bin/python -m pytest -q`。**`TEST_DATABASE_URL` が無いと DB のテスト（ほぼ全部）がスキップされる** |
| フロントエンドの検査 | `cd frontend && npm ci && npm test && npm run build && npm run typecheck`（`typecheck` は `build` の後） |
| 版の整合 | `scripts/check-versions.sh`（Python・Node の版が、各ファイルで揃っているか） |
| 登録語の検査 | `scripts/check-sensitive-terms.sh [A..B]`（語は Git の管理外の `.git/sensitive-terms`。表示しない） |

## 構成（1 つのリポジトリに複数のサービス）

| 場所 | 役割 | 版 |
|---|---|---|
| `backend/` | API（FastAPI）。認証、求人、園、画像、マイグレーション、seed、運営用 CLI | Python 3.13 |
| `frontend/` | 画面（Next.js）。API は画面のサーバー側から呼ぶ。画像の一括生成の道具は `frontend/scripts/generate-images/` | Node 24 |
| `db/` | 初期スキーマ（`schema.sql`）とマスタ（`seed_codes.sql`）。空のボリュームで初めて起動したときだけ流れる | Postgres 17 |
| `jobs/image-gen/` | 画像生成の Cloud Run Job のコード（試作。テスト・CI なし）。**デプロイ済みのジョブとは別物のことがある。正本は [台帳](docs/image-gen-resources.md)** | Python 3.11（**揃えていない。保留中**） |
| `.devcontainer/` | 開発コンテナと、Docker のソケットプロキシ | |
| `_legacy/` `backups/` | 旧 PHP の資料と DB のバックアップ。Git 管理外 | |

版は 1 か所で決めず、`.python-version`（3.13）と `.node-version`（24）を基準にして、`backend/Dockerfile`、`docker-compose.yml` の `frontend`（`node:24-slim`）、
`frontend/package.json` の `engines`、CI が合っているかを `scripts/check-versions.sh` が確かめる。
**未確認:** 開発コンテナの Node は feature `node:2` の既定（最新の LTS）で、24 に固定していない。

## 守ること（コードを書く前に）

- **`.env`・`_legacy/`・`backups/` は読まない。** `.env` には R2 の認証情報が入りうる。`backups/` は個人情報を含みうる DB のダンプ、`_legacy/` は旧システムの資料。
  `grep -r .` や `find .` で潜らない（`git grep` / `git ls-files` を使う）。値を表示・ログ・コミットしない。
- **認証情報は環境変数で渡す。** コード・文書・コミット・スクリーンショットに書かない。`STORAGE_S3_*` の値は特に。画面（`frontend/`）に渡してよいのは公開用の値だけ。
- **ダミーデータの投入は `DEMO_DATA=allow` を渡した開発・テストの環境だけ。** `seed` と `seed-images` を本番の DB に向けない。Compose の `tools` の道具は `up` で起動しない。
- **マイグレーションは番号付き SQL を足すだけ。** 適用済みのファイルを書き換えない（sha256 を記録していて、変わると止まる）。`DROP` / `TRUNCATE` は足さない。
  `db/schema.sql` は 0001 の基準で、`baseline_fingerprint.json` と照合される。適用の前に、必ず DB のバックアップを取る（`docs/image-storage.md`）。
- **`backend/requirements.txt` は直接編集しない。** `requirements.in` を直して作り直す。
- **エラー本文は固定の文。** 例外の文字列やサーバーのパスを API の応答に含めない。
- **権限は API が毎回確認する。** 園は、自分に紐づく求人と画像だけを扱える。他の園のものは 404（存在も分からない）。利用者と園は、アカウントもセッションも Cookie も別。
- **実 API・課金・外部への書き込みは、事前に承認を得る。** 画像の一括生成（Gemini の Batch API）、R2 への書き込み、本番の DB・デプロイ。件数・回数・概算費用を先に示す。
- **画像生成のデプロイ・モデルの変更・保存先の変更は、[台帳](docs/image-gen-resources.md)を更新するまで「完了」にしない。** 台帳の「6. 変更したときの完了条件」に従う。
  デプロイした・実行した・生成に成功した・保存と回収ができた・画面に表示できた、は別々に記録する。成功版の識別は、イメージのダイジェストで行い、`latest` などのタグだけにしない。
  確認は `scripts/inspect-image-gen.sh`（読み取り専用）。担当 AI は、日常の ID では `imagen-app-2026` を読めないので、利用者が実行する。
- **ポートは 3200（画面）と 8200（API）。** 他のローカルのサービスと同時に動かすため。変えない。
- 変更したら、触れた範囲のテストを実行してから報告する。確認できていないこと（Docker のビルド、本物のブラウザーなど）は、確認済みと書かない。

## 保留中（勝手に直さない。方針を示して承認を得てから）

- `jobs/image-gen/`: Python の版（3.11）、モデル名（`gemini-3.1-flash-lite-image`。`frontend/scripts/generate-images/` は `gemini-nano-banana-2.1`）、
  既定のプロジェクト ID がコードに書かれていること。
- 画像生成の「下書き用」モデル（安いモデル）の選定: 記録が見つかっていない（台帳の 2.1 節）。**モデルの確定は保留中**（利用者の指示、2026-11-02）。

## Git

- **コミットメッセージ:** Conventional Commits（`type(scope): 英語の命令形の要約`）。1 コミット 1 論理変更。本文に「なぜ」と確認の結果（限界も）を書く。
- **運用:** `main` に直接コミット。ステージはパスを指定する（`git add -A` と `git add .` は使わない）。コミット前に `git diff --staged` で、意図しない変更が入っていないか確かめる。
- **プッシュ・本番デプロイ・`git reset` / `git restore` は、承認を得てから。** プッシュの前に、追加行の秘密情報と `scripts/check-sensitive-terms.sh origin/main..HEAD` を実行する。
- **CI:** `.github/workflows/ci.yml` が、`main` へのプッシュと PR で、バックエンドのテスト（Postgres 17）、バックエンドの Docker ビルド、フロントエンド（テスト・ビルド・型検査）、
  ワークフローの静的検査を行う。外部 API は呼ばない。デプロイは含まない。

## 作業の進め方

- タスクで指定された範囲だけを編集する。範囲外に必要な変更があれば、勝手に直さず提案する。
- 新しいサービス・言語・フレームワーク・DB を足す前に、ユーザーに確認する。
- 既存の文書は、新規作成より更新を優先する。この CLAUDE.md は短く保ち、詳細は領域の `CLAUDE.md` と `docs/` に置く。
