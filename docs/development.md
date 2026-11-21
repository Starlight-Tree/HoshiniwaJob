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

版の基準は `.python-version` と `.node-version`。`scripts/check-versions.sh` が、Dockerfile（`backend/Dockerfile`・`e2e/web.Dockerfile`）・Compose・`engines`・CI と揃っているかを確かめる。
ポートは画面 3200、API 8200（ほかのローカルのサービスと同時に動かすため、固定）。
Compose の `frontend` は、起動のときに依存を `npm ci` で入れる（`package-lock.json` のとおりに入れ、ロックは書き換えない）。`package.json` と `package-lock.json` が前に入れたときと同じなら飛ばす（再起動のたびに入れ直さない）。依存を変えたら、ホストで `package-lock.json` まで更新してから `docker compose restart frontend`（食い違っていると、`npm ci` が止まってログに出る）。

## テスト

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.in
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres .venv/bin/python -m pytest -q

cd frontend && npm ci && npm test && npm run build && npm run typecheck   # typecheck は build の後。ホストで実行する（開発コンテナの作業ツリーでは npm ci しない）
```

上の検査と、版の整合・compose の構文・`scripts/` のテストを、まとめて流すには `scripts/verify.sh [段]`（段: `backend` `frontend` `lint` `scripts` `all`）。
CI に近い検査で、同じではない（依存の導入とイメージのビルドをしない。Node やツールの版が違いうる。主な違いは、スクリプト冒頭のコメントに書いてある）。
失敗しても残りの段を流し、最後に結果をまとめる。流せない段（DB・venv・PG 17 クライアント・`node_modules`・`actionlint`・`zizmor` が無い、Next.js の勧告の表示で build が止められた）は「未実行」、CI より弱い点は「注記」に出し、合格とは数えない。
終了コードは 0 = 全部合格・注記なし、1 = 失敗あり（未実行があっても 1）、2 = 失敗は無いが未実行か注記あり、64 = 引数の誤り。
副作用は、テスト用 DB の作り直し（`TEST_DATABASE_URL` は、必ずテスト用のサーバーに向ける）と、`frontend/.next` など Git の管理外のファイル。追跡されている `frontend/next-env.d.ts` は build が書き換えるので、終了時に戻す。
`verify.sh`・`scripts/`・`frontend/package.json` の `scripts`・テストを変えたら、流す前に `git diff` で中身を見る（`.claude/settings.json` の許可で、`scripts/verify.sh` は確認なしで動く）。`scripts/` のテストは CI に入っていない。

pytest は直列だけで流す。`pytest-xdist`（`-n auto`）は使えない。テストが DB を固定の名前で作り直す（`hj_test`: `backend/tests/conftest.py`、`hj_seed`: `test_seed_and_cli.py`、`hj_mig_*`: `test_migrate.py`。作り直しは `DROP DATABASE IF EXISTS` → `CREATE DATABASE`。`test_auth.py` と `test_garden.py` は `hj_test` に名前で直接つなぐ）ので、並列にすると同じ DB を取り合って衝突しうる。並列で試した結果ではなく、コードの読みと、ホストの報告（DB 名が固定のため使えない）による。
ホストの報告（2026-11-20。ホストでの計測。コマンド・時間の測り方・生の出力は未受領で、数字はリポジトリから確かめられない）: 直列で 108 件合格・1 件スキップ・13.12 秒（Python 3.13.18・Pillow 13.0.0・pytest 9.2.0。使い捨ての Postgres 17）。スキップの 1 件は、ホストの説明では、実行したイメージに `pg_dump` 17 が無いため（SKIPPED の行は未受領。`test_migrate.py` の `pg_dump` 不在の分岐で、バックアップと復旧の往復のテストが飛んだとみられる。推定）。
スキップがあるので、この実行は CI と `verify.sh` の合格の基準（スキップ 0 件）を満たさない。合格の目安にしない。CI は PG 17 クライアントを入れ、スキップが 1 件でもあれば落とす（`ci.yml` を読んだ内容。実際の CI の実行結果は未確認）。

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

## 園のログインの試行制限と CORS

- **試行制限**（`backend/app/garden.py`。表は `0007_garden_login_attempts.sql`）: メールアドレスごとに数える。IP では数えない（API を呼ぶのは画面のサーバーで、どの利用者も送信元が同じになるため）。窓（既定 15 分。そのメールの最初の試行から）の中で上限（既定 5 回）を超えた試行は、正しいパスワードでも 429（固定の文）。メールが登録済みかどうかで、応答も処理も分けない（登録が無いときも、パスワードの検証と同じ処理を通す）。成功すると、そのメールの数えを消す。窓の 2 倍より古い行は、ログインのついでに消す。
- 表には、正規化（前後の空白を除き小文字）したメールの SHA-256 だけを置き、生のメールは置かない（形は CHECK で縛る）。ハッシュは秘密ではない（推測しやすい文字列は、辞書で元に戻せることがある）ので、表を読める人は絞る。
- 設定（環境変数）: `GARDEN_LOGIN_MAX_FAILURES`（既定 5。1〜1000）、`GARDEN_LOGIN_WINDOW_MINUTES`（既定 15。1〜10080）。整数でない値・範囲外は、API の起動で止まる（別の値には切り替えない）。
- 限界: そのメールを知っている人が、わざと失敗を重ねると、その園のログインを窓の間だけ止められる（正当な利用者も入れなくなる）。IP の制限・CAPTCHA は無い。
- **CORS**（`backend/app/main.py`）: `CORS_ORIGINS`（既定 `http://localhost:3000`）の許可元に、GET・POST・PUT・PATCH・DELETE を許す。画面は API をサーバー側から呼ぶので、ふだんはブラウザーの CORS を通らない。
- 確認（2026-11-21。ホストの使い捨ての Postgres 17 で `pytest -q -rs`）: 試行制限は `tests/test_garden.py`、CORS は `tests/test_main.py`、設定値は `tests/test_settings.py`、表の形は `tests/test_migrate.py`。本番の DB への適用と、実際のブラウザーでの確認は未実施。

## E2E（表示名の保存）

「Google ログイン後の画面で、アカウントのメニューから表示名を変更して保存し、画面と API の DB に反映される」までを、Playwright で自動テストする（`e2e/`）。

- **確かめること**: ログイン済みの画面でアカウントメニューを開き、「表示名を変更」で名前を変えて保存すると、メニューのボタンが新しい名前になり（再読み込みしても同じ）、`users.display_name` が新しい名前になる。対照として、別の秘密で署名した Cookie ではログインしていない表示になること（署名が検査されていること）も確かめる。
- **確かめないこと**: 本物の Google との往復（同意画面・コールバック）。https の Cookie（名前が `__Secure-` で始まる経路）。この E2E は http の `http://web:3000` だけで動く。Google の代わりに、Better Auth のセッションを模した状態（`auth_user`・`auth_session` の行と、署名つきの Cookie）を、使い捨ての DB に注入する（`e2e/support/session.ts`）。
- **実行**: `e2e/run.sh`（リポジトリのルートからでも、どこからでも）。ホストに要るのは Docker だけ（Playwright もブラウザーも Node も要らない）。ホストにポートを公開せず、名前付きボリュームも作らない。開発スタック（`jobnavi`。3200・8200）とは別のプロジェクト（`jobnavi-e2e`）で、開発の DB・コンテナには触らない。
- **しくみ**: `e2e/compose.yml` が、使い捨ての DB（tmpfs。DB 名は `jobnavi_e2e`）・API・画面（`next build` → `next start`）・Playwright を起動し、終わったら `down -v` で全部消す（失敗しても）。ビルドしたイメージ（`jobnavi-e2e-*`）だけ、次回を速くするため残る。初回は、イメージの取得と `next build` で時間がかかる。失敗時の trace・スクリーンショットは、`e2e/test-results`（Git 管理外）に出る。
- **秘密**: Better Auth の署名の秘密と DB のパスワードは、実行ごとに乱数で作る使い捨ての値（ファイルにもログにも出さない）。本物の値（`BETTER_AUTH_SECRET`・Google・R2）は使わない。Google の OAuth の値は、設定の検査を通すための固定のダミー。
- **版を上げたとき**: Cookie の署名の作り方は、Better Auth 1.7.18 の挙動を `e2e/support/session.ts` に写したもの（Better Auth をテスト側には入れていない）。`frontend/package.json` の `better-auth` の版を上げたら、E2E を流して確かめ直す（合わないと「注入したセッションを Better Auth が認めませんでした」で落ちる）。Playwright は、`e2e/package.json` の `@playwright/test` と `e2e/Dockerfile` のイメージの版（どちらも 1.65.1）を必ず同じにする。
- **CI には入れていない**（`ci.yml` は変えていない）。

## 画像の生成

`frontend/scripts/generate-images/`（Gemini の Batch API。課金される。手順は同じ場所の README）。生成した画像は `python -m app.images_cli register` で登録する。

## CI

[.github/workflows/ci.yml](../.github/workflows/ci.yml)。`main` への push と PR で、バックエンドのテスト（Postgres 17）、バックエンドのイメージのビルド、フロントエンドのテスト・ビルド・型検査、ワークフローの静的検査を行う。外部の API は呼ばず、デプロイは含まない。

## 秘密の検査

コミットの前後に、登録した語（実プロジェクト ID など）が入っていないかを `scripts/check-sensitive-terms.sh` で検査できる。語は Git の管理外の `.git/sensitive-terms` に置く（リポジトリには置かない。エージェントは、この中身を読まず、表示しない）。台帳に書いてよいプロジェクト ID と、登録語に入れた語は別で、登録語に当たるものは書かない。
