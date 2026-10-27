# 画像の管理（求人・法人）

求人と法人の画像を、**本体はオブジェクトストレージ、対応は DB、コードと一覧は Git** に分けて管理する。画像が増えても、コードの修正・再デプロイ・Git への画像の追加は要らない。

```text
ブラウザー ── 画面（Next.js）── API（FastAPI）── DB（images / recruit_images / garden_images）
                 │                    └── 保存先（公開側 / 非公開側）
                 └── next/image ── 公開 URL（CDN の独自ドメイン。ローカル開発は /media）
```

## 仕組み

- **画像の状態**（`images.status`）: `uploading`（登録の途中）→ `pending`（検証済み・**非公開側だけ**にある）→ `publishing` → `approved`（公開側へ複製済み・公開してよい）。ほかに `rejected`（却下）、`deleted`（実体を消した記録）。
- **公開側に置くのは、承認済みの画像だけ。** 公開 API が返すのも `approved` だけ。承認（公開）と却下は運営だけ（`python -m app.images_cli`）。園の API からは呼べない。
- **登録は 1 つの関数を通る**（`app/image_service.py`）: 園のアップロード、運営の CLI、ダミー画像の seed が同じ検証・登録・承認を使う。
  検証は、形式（JPEG・PNG・WebP のみ。SVG・GIF・アニメーションは不可）、容量（既定 5MB）、寸法（短辺 200px 以上、4000 万画素まで）、実データ（Pillow で読み込めること）。
  配信用には、EXIF・GPS・ICC・テキストを除いて再エンコードしたものを保存する（向きは画素に反映する。長辺は 2400px まで）。
- **保存キーは `images/<uuid>.<拡張子>`。** 画像の更新は、同じキーに上書きせず、新しい画像として登録して DB の参照を切り替える（保存部品は、同じキーへの別の内容の書き込みを拒否する）。署名付き URL は作らず、DB にも持たない（公開 URL は保存キーから組み立てる）。
- **求人の画像**は `recruit_images`（表示順 `position`、ヒーロー `is_hero`）。ヒーローは求人ごとに 1 枚まで（DB の一意索引）で、承認済みの画像だけ（DB のトリガー）。指定が無ければ、公開 API は表示順で先頭の承認済みの画像を `hero_image` にする。画像が 1 枚も無ければ、画面は共通の代替画像（`public/images/generated/job-detail-sample.jpg`。Git 管理）を出す。
- **法人の画像**は `garden_images`（`logo` / `banner`）。同じ `images` を使う。API（`/api/garden/profile-images`）と DB はあるが、**画面と公開側の表示は未実装**（法人の紹介ページができてから）。
- **権限**: 園が操作できるのは、自分に紐づく求人（`recruits.garden_account_id`）と自分の画像だけ。確認は API が毎回 SQL の条件で行い、他の園のものは 404（存在も分からない）。承認前の画像のプレビューも、認証と所有権の確認を通った場合だけ（`/api/garden/images/{id}/preview`。画面は `/garden/images/{id}/preview` で中継）。

## 設定（環境変数）

| 名前 | 意味 |
|---|---|
| `STORAGE_BACKEND` | `local`（既定。フォルダー。開発・テスト用）/ `s3`（S3 互換。Cloudflare R2 など） |
| `STORAGE_LOCAL_DIR` | local の保存先（既定 `/data/media`。Compose では名前付きボリューム `dev-media`） |
| `IMAGE_PUBLIC_BASE_URL` | 公開画像の URL の頭。s3 では CDN の独自ドメイン（例 `https://img.example.com`）。local は `/media`。**画面（Next.js）にも同じ値を渡す** |
| `STORAGE_S3_ENDPOINT_URL` | S3 互換のエンドポイント。R2 は `https://<アカウント ID>.r2.cloudflarestorage.com`（地域指定のバケットは別の形。後述の出典） |
| `STORAGE_S3_PUBLIC_BUCKET` / `STORAGE_S3_PRIVATE_BUCKET` | 公開用 / 非公開用のバケット名。**別にする**（同じ名前は起動時に拒否） |
| `STORAGE_S3_ACCESS_KEY_ID` / `STORAGE_S3_SECRET_ACCESS_KEY` | 保存先の認証情報。環境変数かシークレット管理でだけ渡す。ログ・Git・画面に出さない |
| `IMAGE_MAX_UPLOAD_BYTES` | アップロードの上限（既定 5MB） |

s3 で必要な設定が 1 つでも欠けると、API は起動に失敗する（local に切り替えない）。開発用と本番用は、**バケットも認証情報も別**にする。

## 使い方

**園（画面）**: <http://localhost:3200/garden> にログイン →「求人の画像」から求人を選び、画像の追加・並べ替え・ヒーローにする・削除の依頼ができる。登録した画像は「承認待ち」で、運営が承認するまで公開されない。削除の依頼は求人から外すだけで、実体は猶予のあとの掃除で消える。

**運営（CLI。DB と保存先の認証情報を持つ人だけ）**: コンテナの中で実行する（例: `docker compose run --rm api python -m app.images_cli list --status pending`）。

```bash
python -m app.images_cli list [--status pending]
python -m app.images_cli approve <画像ID>      # 公開側へ複製して公開
python -m app.images_cli reject <画像ID>       # 却下・公開の取り消し（公開側の実体も消す）
python -m app.images_cli register FILE --alt "説明" --recruit-id 5 [--approve --hero]
python -m app.images_cli reconcile [--apply] [--grace-days 30] [--stuck-hours 1]
python -m app.images_cli formfile              # recruits.formfile に値のある求人の一覧
```

**画像を足しても、コードの変更・再デプロイは要らない**（園の画面か CLI で登録すれば、DB の関連だけで表示が変わる）。

## 失敗したときの整合（DB とストレージが食い違ったままにしない）

先に DB へ意図（`uploading` / `publishing`）を書き、そのあとストレージを触る。どの段階で止まっても、次のようになる。

- 登録の途中で失敗 → 作りかけの行と実体を消す。消せなければ `uploading` のまま残り、`reconcile` が（実体があり sha256 が一致すれば）`pending` に進める。なければ `deleted` にする。
- 承認の途中で失敗 → 公開側の複製を消して `pending` へ戻す。戻せなければ `publishing` のまま残り、`reconcile` が承認をやり直す。承認は何度やっても同じ結果になる。
- 却下したのに公開側に実体が残った → `reconcile` が消す（公開側にあるのは `approved` / `publishing` だけ、が不変条件）。
- 参照されている画像（`recruit_images` / `garden_images`）は消さない（DB も `ON DELETE RESTRICT`）。外れた画像は、猶予（既定 30 日）のあとに `reconcile --apply` が物理削除する（行は `deleted` として残す）。差し替えた直後には消さない。
- `reconcile` は既定が dry-run（一覧だけ）。`--apply` で実行する。定期的に dry-run を見て、問題なければ `--apply` する運用を想定（定期実行の仕組みは未導入）。

## マイグレーション（`app/migrate.py`）

番号付き SQL（`app/migrations/NNNN_名前.sql`）と小さな実行器。API は生の psycopg3 で SQLAlchemy を使っていないため、Alembic ではなくこの方式にした（Alembic の利点であるモデルとの差分生成が使えない）。

- `0001` は初期スキーマ（`db/schema.sql` と `db/seed_codes.sql`。Postgres の初回起動で流れる）。実行器はこれを流さず、**表・列・制約・索引・マスタの件数が `baseline_fingerprint.json` と一致したときだけ**「適用済み」と記録する。1 つでも違えば、何も記録せず止まる。
- 適用済みのファイルは sha256 を記録し、書き換えを検出して止まる。直すときは新しい番号のファイルを足す。
- 1 ファイル 1 トランザクション（`lock_timeout` 5 秒）。失敗したら何も変えない。同時実行はアドバイザリーロックで防ぐ。
- 確認: `python -m app.migrate --status`（読むだけ）/ `--dry-run`（適用予定と事前検査だけ）/ 引数なしで適用。
- `0002_images.sql` は新しい表の作成と、`recruits.demo_key`（NULL 可・既定値なしの列）の追加だけ。**既存のデータ・ID・`formfile` は変えない。** `recruits` への ALTER は一瞬の排他ロック。DROP・TRUNCATE・リセットは含まない。
- `recruits.formfile`（「画像ファイル」の列）は残してある。値のある求人は `formfile` で確認できる（ダミーデータでは 0 件の想定）。値と使用箇所の確認が済んでから、別のマイグレーションで外す。

## バックアップと復旧

マイグレーションの前に、必ずバックアップを取る（`backups/` と `*.dump` は Git に入れない）。

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U hoshiniwa -Fc hoshiniwa > backups/hoshiniwa-$(date +%Y%m%d-%H%M).dump
```

復旧（別の DB へ戻して中身を確かめてから、必要なら入れ替える）:

```bash
docker compose exec -T db psql -U hoshiniwa -d postgres -c "CREATE DATABASE hoshiniwa_restore"
docker compose exec -T db pg_restore -U hoshiniwa --no-owner -d hoshiniwa_restore < backups/<ファイル>.dump
```

- 画像の本体は DB のバックアップに入らない。**ストレージ側の保護**が別に要る（R2 ではバケットの保護・バージョニング相当の運用を決める。決めるまでは、`reconcile --apply` を実行しない）。
- 画像が失われても、DB の行（`storage_key` と `sha256`）から、何が足りないかが分かる。ダミー画像は、下の手順で再生成なしに復元できる。

## 新しい環境（ダミー画像の復元）

通常の `docker compose up` は、マイグレーションもダミーデータも流さない。新しい環境では、README の「初めての環境」の順に、`migrate` → `seed` → `seed-images` を 1 回ずつ実行する（いずれも `profile: tools` の道具で、`up` では起動しない。`seed` と `seed-images` は `DEMO_DATA=allow` が無いと実行を拒否する）。ダミー画像の元ファイルは `frontend/public/images/generated/recruits/`（Git 管理。マニフェストは `backend/app/demo_images.json`。元ファイルの sha256 が一致しなければ使わない）。
同じことは単独でもできる（何度実行しても、画像も関連も増えない）。

```bash
docker compose run --rm seed-images
# 画像の置き場（https。マニフェストの file 名を末尾に足して取る）から復元するとき
docker compose run --rm seed-images python -m app.seed_images --source-url https://<配信ドメイン>/demo/
```

## Cloudflare R2 を使うとき

**この節の操作は、まだ実行していない。** バケット作成・公開設定・DNS・API トークンの作成は、対象と設定を示して承認を取ってからにする。

- 必要なもの: Cloudflare のアカウント（R2 を有効にした状態）と、**同じアカウントに zone として登録されたドメイン**（公開バケットの独自ドメインの条件）。`r2.dev` は開発用で本番に使わない。
- 作るもの（星庭ジョブ専用。ほかのプロジェクトのバケット・設定・認証情報は流用しない）: 公開用バケット 1 つ（独自ドメインを接続）、非公開用バケット 1 つ（公開設定にしない）、開発用に同じ組をもう 1 組。
- API トークン: R2 の **Object Read & Write** を、**この 2 つのバケットだけ**に絞って作る（Admin 権限は使わない）。作成直後にだけ表示される Secret Access Key は、会話・Git・ログ・スクリーンショットに出さず、環境変数かシークレット管理へ直接入れる。
- 費用の見積もり条件（出典: Cloudflare 公式の料金ページ。等級 B）: Standard ストレージ 10 GB-月・Class A（書き込み・一覧）100 万回/月・Class B（読み取り）1000 万回/月が無料枠、超過分は $0.015/GB-月・Class A $4.50/百万回・Class B $0.36/百万回、**外向きの転送（egress）は無料**。現在の画像は約 10MB（12 枚）で、無料枠に収まる見込み。支払い方法の登録が要るかは、公式ページに記載がなく未確認。
- 出典: <https://developers.cloudflare.com/r2/pricing/> / <https://developers.cloudflare.com/r2/buckets/public-buckets/> / <https://developers.cloudflare.com/r2/api/tokens/>

## 未実装・未確認

- 実際の R2 への接続（S3 互換の部分は、モックの S3（moto）でだけ確かめた。R2 実機での動作、CDN のキャッシュ、独自ドメインの設定は未確認）。
- 法人画像の画面と公開側の表示。園のアップロードの自動承認・審査の画面（承認は CLI のみ）。
- 掃除（`reconcile`）の定期実行。ストレージの保護・復旧の運用（R2 側）。
- 画像のウイルス・不適切な内容の検査（形式・寸法・実データの検証だけ）。
