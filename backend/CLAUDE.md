# backend/（API）

全体の方針・禁止事項は、ルートの [CLAUDE.md](../CLAUDE.md)。画像・マイグレーション・バックアップの詳細は [docs/image-storage.md](../docs/image-storage.md)。

FastAPI + psycopg3（生の SQL。ORM・Alembic は使わない）。Python 3.13（`Dockerfile`）。依存は `requirements.in` と `requirements-dev.in`、固定版が `requirements.txt`（直接編集しない）。

## モジュール（`app/`）

| ファイル | 役割 |
|---|---|
| `main.py` | アプリの組み立て。ルーターの登録、CORS、`/health`。`/media` は `STORAGE_BACKEND=local` のときだけ |
| `settings.py` | 環境変数の読み取り。設定はここに集める。必須の値が無いときは起動に失敗させ、別の値に切り替えない |
| `db.py` | 接続プール（`dict_row`） |
| `auth.py` / `garden.py` / `security.py` | 利用者と園のログイン。表もセッションも別。共通の部品（トークン・argon2）は `security.py`。利用者は、Google でのログイン（`POST /api/auth/google`）と、お名前の変更（`PATCH /api/auth/me`）もここ |
| `google_login.py` | Google でのログインの、コードの交換と ID トークンの検証（iss・aud・exp・nonce・email_verified。署名は、Google から TLS で直接受け取るので省く。理由は冒頭）。クライアントのシークレットは、この API だけが持つ。標準ライブラリだけで通信する（依存を足さない） |
| `recruits.py` / `schemas.py` | 求人の検索・詳細・条件ごとの件数（`/api/facets`）と、応答の型 |
| `images_api.py` / `image_queries.py` / `image_service.py` / `storage.py` | 画像。API、検索用の SQL、検証・登録・取り下げ・点検、保存先（`LocalStorage` / `S3Storage`） |
| `images_cli.py` | 運営用 CLI（`list` `register` `reject` `reconcile` `formfile`）。園の API からは呼べない |
| `migrate.py` / `migrations/` | 番号付き SQL の実行器と、`0002` 以降のファイル。`baseline_fingerprint.json` は 0001 の照合用 |
| `seed_demo.py` / `seed_images.py` / `demo_images.json` | ダミーデータ。`DEMO_DATA=allow` が無いと実行を拒否する |

## 守ること

- **SQL の値は必ずパラメータで渡す。** f-string で組み立ててよいのは、固定の断片（表名・条件の骨組み）だけ（`recruits.py` の `clause`）。
- **画像の登録は `image_service.register_image` を通す。** 園のアップロード、運営の CLI、seed が同じ検証・登録を使う。別の経路で `images` に書かない。
  保存キーは `images/<uuid>.<拡張子>`。同じキーへの別の内容の上書きはしない（更新は新しい画像として登録）。署名付き URL は作らない。
- **先に DB へ意図を書き、そのあとストレージを触る。** 削除は先に DB を確定してから実体を消す。この順を変えない（食い違いの設計は `image_service.py` の冒頭）。
- **マイグレーション:** `migrations/NNNN_名前.sql` を足すだけ。適用済みを書き換えない・`DROP` / `TRUNCATE` を入れない。`db/schema.sql` を変えたら、`baseline_fingerprint.json` と `test_migrate.py` の整合を確かめる。
- **エラー本文は固定の文。** 例外の文字列を `detail` に入れない。認証の失敗は、メールの有無が応答の速さや文面から分からないようにする（`security.py`）。
- **権限の確認は API の SQL の条件で行う。** 画面を信用しない。他の園のものは 404。
- `DEMO_DATA`、`STORAGE_S3_*` などの認証情報は、環境変数だけで受け取る。ログ・例外に出さない。
- 新しい依存は `requirements.in` に足して `requirements.txt` を作り直す（README に「uv が使える環境では `uv pip compile`」とある）。作り直しは差分が大きくなるので、先に確認する。

## テスト（`tests/`）

- `pytest`（`pytest.ini`: `testpaths = tests`、`pythonpath = .`）。**`TEST_DATABASE_URL`（Postgres 17）が無いと DB のテストはスキップされる。** スキップのまま通っても、検証したことにならない。
- `conftest.py` の `client` は、セッション単位で `hj_test` を作り直し、`db/schema.sql` と `seed_codes.sql` → `migrate` → `seed_demo --reset` を流す。マイグレーションのテストは、別名の DB を `new_database` で作る。
- 外部のサービスは呼ばない。S3 は `moto`。画像はテスト用に作る（`imagefiles.py`）。保存先はテスト用の一時フォルダー。
- 新しいテストは、対象のモジュール名に合わせた `test_<対象>.py` に足す。補助モジュールは `test_` で始めない。

## 実行

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.in
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres .venv/bin/python -m pytest -q
```

lint・整形（ruff など）は未導入。導入するときは、別の提案として承認を得る。
