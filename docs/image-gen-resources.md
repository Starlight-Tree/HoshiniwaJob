# 画像生成ジョブの台帳（試作）

Vertex AI で画像を生成する Cloud Run Job について、**何が・どこに・どの設定でデプロイされ、何が成功したか**の記録。
このジョブは、docunavi のヒーロー画像のために作った試作で、星庭ジョブのアプリ本体（`backend/` `frontend/`）からは使っていない。星庭ジョブで画像生成を使うときの土台として残してある。

- 最終更新: 2026-11-02（以降、ジョブは変更・実行していない）
- 各行の「状態」に、確認の根拠を書く。**確認できていないことは「未確認」と書く**（推測で埋めない）。
- 秘密情報（キー・トークン・DB の接続文字列）、資料の本文、機密を含むプロンプトは書かない。プロジェクト ID やリソース名は秘密ではないので書く。

状態の凡例:

| 状態 | 意味 |
|---|---|
| 報告 | 運用者がコンソールまたは `gcloud` で見て報告した内容。**生の出力はこのリポジトリに無い**（取得したら `docs/image-gen-evidence/` へ。8 節） |
| ソースで確認 | このリポジトリのコミットを読んだ。**デプロイ済みの設定とは別物**（4 節） |
| 未確認 | まだ誰も見ていない |

## 1. 区別すること（混ぜない）

| 軸 | 値 | 備考 |
|---|---|---|
| コードの管理先 | このリポジトリの `jobs/image-gen/` | 成功した実行のイメージの元のコードがここにあるかは**未確認**（2 節・4 節） |
| ジョブの配置先（プロジェクト） | `imagen-app-2026` | docunavi の本番とは別のプロジェクト。費用の超過が本番の停止に波及しないようにしている |
| ジョブの配置リージョン | `asia-northeast1` | Cloud Run Job と Artifact Registry の場所 |
| Vertex AI の location | `global` | モデルを呼ぶ場所。配置リージョンとは別の概念 |
| デプロイ済みの設定 | 2 節・3 節 | 実際に動いたもの |
| ソースの設定 | 4 節 | **デプロイ済みとは限らない** |

## 2. デプロイ済みの設定

| 項目 | 値 | 状態 |
|---|---|---|
| ジョブ名 | `image-generation-job` | 報告 |
| 正確なモデル ID（2026-10-29 の成功した実行） | `gemini-3.1-flash-lite-image` | 報告。イメージ内の `/app/main.py` での確認は**未** |
| 呼び出し方式 | **未確認**（`generate_content` か別か） | |
| イメージ（成功した実行） | `asia-northeast1-docker.pkg.dev/imagen-app-2026/image-repo/imagen-fast-job@sha256:ae0fbf302a87d2c8bbdf2df0524a394cc7302db8282cba7b35e308988f64eeac` | 報告。ダイジェストで固定。**`latest` などのタグは、成功版の識別に使わない** |
| 対応するソースコミット | **未確認** | 4 節 |
| イメージ（現在） | `asia-northeast1-docker.pkg.dev/imagen-app-2026/image-repo/docunavi-hero-job@sha256:db1e9cd35528902a02c155c4db3af719306beace40fe432e96486acbbc20ed51`（成功した実行の `imagen-fast-job` とは別のイメージ名） | 報告（2026-11-02）。成功した実行のイメージと同じかは**未確認** |
| 実行サービスアカウント（現在） | `hero-image-job@imagen-app-2026.iam.gserviceaccount.com`。役割は `roles/aiplatform.user` だけ（`editor` なし、キーなし） | 報告（2026-11-02）。IAM の生の出力は未受領 |
| 実行サービスアカウント（成功した実行の時点。復旧用） | 既定の Compute Engine サービスアカウント。`roles/aiplatform.user` と `roles/editor` を持つ（権限は変えていない） | 報告 |
| タスク数・再試行（成功した実行） | `taskCount: 2`、`maxRetries: 1` | 報告 |
| タスク数・再試行（現在） | `taskCount: 5`、`maxRetries: 0`、並列数は未設定（既定） | 報告（2026-11-02）。変更の日時と操作は未確認 |
| 環境変数・Secret（現在） | 名前: `GOOGLE_CLOUD_PROJECT`、`GOOGLE_CLOUD_LOCATION`、`R2_BUCKET`、`R2_ACCOUNT_ID`、`R2_TEMP_CREDENTIALS`。うち `R2_TEMP_CREDENTIALS` は Secret `r2-docunavi-hero-write-temp`（版 `latest`）への参照。`PLAN_JSON` と `PLAN_SHA256` はジョブの定義に無く、実行時に `--update-env-vars` で渡す | 報告（値は出していない） |
| Secret Manager（親トークン用） | 空の Secret `r2-docunavi-hero-parent` を作成済み（版なし）。誰にも `secretAccessor` を付けない方針 | 報告。版の有無と IAM は**未確認** |
| 出力先・回収 | **Cloudflare R2**（バケット `hoshiniwa-images`、prefix `docunavi-hero/<資料 ID>/<plan ハッシュ先頭 16 文字>.png`。名前は `.png` だが中身は JPEG の場合がある）。書き込みは `If-None-Match: *` で、既存は上書きしない。回収は、読み取り専用の一時キーで取り出す（3.2）。**3.1 の動作確認の実行の時点では、コンテナ内のファイルだけで、画像は失われた** | 3.2 の実行で保存と回収を確認。生のログは未受領 |
| ジョブの現在の最新の版（generation） | **未確認** | |
| 成功したイメージが Artifact Registry に残っているか | **未確認** | 掃除のルールで消えていないか（5 節の手順 5） |

### 2.1 モデルの 3 区分（混ぜない）

| # | 区分 | 値 | 状態 |
|---|---|---|---|
| 1 | 2026-10-29 に成功したモデル | `gemini-3.1-flash-lite-image` | 報告。イメージ内での確認は**未** |
| 2 | その後に、下書き用（安いモデル）として選んだモデル | **特定できていない** | 記録が見つかっていない。**モデルの確定は保留中** |
| 3 | 現在デプロイされているモデル | **未確認** | 現在のイメージのダイジェストの中身を、まだ読んでいない |

リポジトリのコミット・ファイルに現れるモデル名は、`gemini-nano-banana-2.1`（`frontend/scripts/generate-images/`。API キーの経路）と `gemini-3.1-flash-lite-image`（`jobs/image-gen/main.py`）の 2 つだけ。
名前に `fast` / `lite` が付くことだけでは、「安い下書き用」の根拠にしない。
2 と 3 は、`scripts/inspect-image-gen.sh` の「ジョブの現在の定義」と「リポジトリのイメージ一覧」で確かめる（読み取りのみ）。成功した実行より後に作られたイメージがあれば、その `/app/main.py` を `--read-source` で読む。

### 2.2 実行身分と費用の扱い（運用ルール）

- 成功した実行の実行身分は、既定の Compute Engine サービスアカウント（`roles/editor` を持つ）。**VM は起動しておらず、VM の費用は発生しない**（報告）。ただし `editor` は広く、ジョブのコードの誤りや取り込んだ入力の指示で、他のリソースを変更・削除できてしまう。
- 2026-11-02 に、専用のサービスアカウント `hero-image-job`（`roles/aiplatform.user` のみ）へ切り替えた。`aiplatform.user` だけで `generate_content`（`global`）が通るかは、実行するまで**未確認**。
- 出力先への書き込みは、IAM ではなく R2 の一時キー（`PutObject` / `HeadObject`、`docunavi-hero/`、15〜30 分）で行う。親トークンの Secret には、誰にも権限を付けない。
- **1 回の `execute` の生成呼び出しの上限は `taskCount × (1 + maxRetries)`**（現在は 5 × 1 = 5 回）。実行の前に、題材・枚数・費用の扱いを示して承認を得る。`scripts/inspect-image-gen.sh` が、ジョブの設定から計算して表示する。
- 実行の前に、出力の回収方法（保存先がコンテナ内だけではないこと）を確認する。確認できないうちは実行しない。失敗しても自動で再実行しない。
- 結果は「ジョブ成功」「画像生成 API の成功」「保存」を分けて報告する。ジョブ成功だけでは、画像生成の成功とみなさない（ログの API 応答と保存の行、出力先の新しいオブジェクトで確かめる）。

## 3. 成功した実行（記録）

実行 ID `image-generation-job-fjtcv`、成功日時 2026-10-29 13:41 UTC。すべて「報告」で、生の出力は未受領。

| 段階 | 結果 |
|---|---|
| デプロイした | 実行時のイメージは 2 節のダイジェスト。いつ・どのコマンドでデプロイしたかは**未確認** |
| 実行した | 実行一覧で 2/2 タスクが完了 |
| 画像生成に成功した | 両タスクのログに画像保存の行と `exit(0)` |
| 画像を保存・回収できた | **未確認**。ログに出たファイル名は `output_task0_0.png` と `output_task1_0.png` |
| 画面に表示できた | **未** |

### 3.1 動作確認の実行（2026-11-02、1 回）

ジョブ成功、画像生成 API は 2 回とも成功。保存先はコンテナ内のローカルファイルで、GCS へのアップロードは無く、**画像は回収できない**（終了後に失われる）。実行 ID と生のログは未受領。
この実行から分かったのは、「画像生成 API を呼べる」ことだけ。

「デプロイした」「実行した」「生成に成功した」「保存・回収できた」「画面に表示できた」は、別々に記録する。1 つが済んだことを、次が済んだことにしない。

### 3.2 R2 へ保存した実行（2026-11-02）

| 回 | 内容 | 結果 |
|---|---|---|
| 1 回目（ヒーロー 1 枚） | docunavi の資料 4 の画像。実行 ID `image-generation-job-z6fgz`。R2 のオブジェクトは `docunavi-hero/4/1179505c52d20892.png` | 保存に成功し、docunavi の DB に取り込んで承認し、本番に表示された |
| 2 回目（5 枚） | 資料 1・2・3・5・6。`max_images: 5`、モデル `gemini-3.1-flash-lite-image`、16:9。plan の SHA-256 先頭は `3200171cc78f8b84` | ジョブ成功、5 枚すべてが R2 に保存、エラーなし、生成呼び出しは 5 回。取り出したファイルの大きさはログと一致し、先頭バイトは 5 枚とも JPEG。目で確かめ、docunavi に取り込んで承認した |

**実行の手順（運用者がホストで行う）**

1. 親の鍵（Secret `r2-docunavi-hero-parent` の JSON）を標準入力に流し、`scripts/issue-r2-temp-credentials.py --kind write`（`--ttl 1200`）で、書き込み用の一時キーをローカルで署名する。
2. 一時キーを、Secret `r2-docunavi-hero-write-temp` の**新しい版**として追加する（ジョブは `latest` を参照する）。
3. `gcloud run jobs execute image-generation-job --wait --update-env-vars` で、`PLAN_JSON` と `PLAN_SHA256` を渡して実行する。
4. 終了時に、追加した版を破棄する（失敗しても破棄する）。

取り出しは、`--kind read`（`--ttl 900`）で署名した一時キーを、使い捨てのコンテナに環境変数で渡して行う。保存済みの資料は、再実行しても生成を呼ばない（保存の有無を先に確かめる）。
**未確認:** 1 枚あたりの単価と請求額、一時キーの版が破棄されたことの確認出力、`taskCount` を 5 にした操作。

## 4. ソースとデプロイの関係（混ぜない）

| コミット | 日時 | 内容 | デプロイ |
|---|---|---|---|
| `71bb2c5` | 2026-10-31 | `jobs/image-gen/` の最初のコミット。モデル `gemini-3.1-flash-lite-image`、プロジェクトの既定 `imagen-app-2026`、場所の既定 `global`、縦横比 1:1、出力はコンテナ内のファイルだけ | **未確認**（成功した実行は 10-29 で、このコミットより前） |
| `6c01342` | 2026-11-01 | 承認済みの `plan.json`（GCS）を読み、PNG を GCS へ書く版 | していない |
| R2 版（現在の `jobs/image-gen/`） | 2026-11-02 | `6c01342` の GCS を、Cloudflare R2（S3 互換 API、`boto3`）に書き換えた版。偽の S3・偽の genai のテストが通る（実 API・実 R2・通信なし） | **デプロイ済みと読める（報告）**。現在のジョブ（`docunavi-hero-job`）は、この版だけが読む環境変数を使い、3.2 の実行で R2 への保存と回収を確認した。**ただし、ビルド元のコミットが無く**、デプロイしたイメージとこの版が同一かは、イメージ内の `/app/main.py` を読むまで未確認 |

**保存先の決定（2026-11-02）:** R2 が正規で、GCS は使わない。既存バケット `hoshiniwa-images`、prefix `docunavi-hero/`、バケットロックなし、r2.dev は使わない。
ジョブには親トークンを渡さず、親から署名した一時キー（書き込み用: `PutObject` + `HeadObject`、取得用: `GetObject` + `HeadObject`。どちらも `docunavi-hero/`、15〜30 分）だけを渡す。
親は、既存の Account API token `hoshiniwa-images-rw`（`hoshiniwa-images` のみ、期限 2027-04-27）。**既存トークンなので、作業後に削除はできない**（同じキーを使う星庭ジョブの画像の保存が止まる）。漏えいの疑いがあるときは、このトークンを再発行（roll）し、`STORAGE_S3_*` も差し替える。

成功した実行（2026-10-29）は `71bb2c5` より前で、イメージ名（`imagen-fast-job`）もこのリポジトリのパスと一致しない。したがって、リポジトリのコードは**成功したイメージの元のコードとは限らない**。既存ジョブを `6c01342` で上書きしない。

## 5. 確認の手順（読み取り専用）

`scripts/inspect-image-gen.sh`。画像生成・デプロイ・IAM の変更・DB の変更は行わない（使う `gcloud` は `run jobs list/describe`、`run jobs executions list/describe`、`artifacts docker images describe`、`logging read` だけ。`--read-source` のときだけ `docker pull` と、`--entrypoint` を上書きした `docker run`）。
出力は秘密のパターンとプロンプトの本文を伏せるが、完全ではない。テストは `scripts/test-inspect-image-gen.sh`（偽の `gcloud` と `docker`。実際の `gcloud` に対する動作は**未確認**）。

```bash
scripts/inspect-image-gen.sh                  # ジョブ・実行・イメージ・ログ（直近の成功した実行）
scripts/inspect-image-gen.sh --read-source    # さらに、そのダイジェストのイメージから /app/main.py を読む（docker が要る）
IMAGEN_EXECUTION=image-generation-job-fjtcv scripts/inspect-image-gen.sh   # 実行を指定
```

必要な権限（読み取りだけ。付与は書き込みなので、権限を持つ人が行う）:

- Cloud Run: `run.jobs.get` `run.jobs.list` `run.executions.get` `run.executions.list`
- Logging: `logging.logEntries.list`
- Artifact Registry: `artifactregistry.dockerimages.get`（`--read-source` は、さらに `artifactregistry.repositories.downloadArtifacts`）

ジョブが Vertex AI を呼ぶ側の権限（実行サービスアカウントの `aiplatform.user` など）は**未確認**。

## 6. 変更したときの完了条件

画像生成のデプロイ、モデルの変更、保存先の変更を行ったら、次をこの台帳に書き終えるまで「完了」にしない。

1. 2 節の該当行（モデル ID、呼び出し方式、イメージのダイジェスト、サービスアカウント、タスク数・再試行、出力先）
2. デプロイしたイメージの**ダイジェスト**と、**ソースコミット**（確認できたものだけ。確認できなければ「未確認」）
3. 動作確認に使った**実行 ID**
4. 3 節の 5 段階（デプロイ・実行・生成成功・保存と回収・画面表示）を、それぞれ別に。成否と保存先
5. 未確認のまま残ったこと
6. 復旧方法（7 節）
7. 確認した出力を `docs/image-gen-evidence/` へ（秘密を除いたもの）

`latest` などのタグだけを、成功版の識別情報として残さない。

## 7. 復旧方法

成功した実行のイメージ（2 節のダイジェスト）へ戻す。**書き込みなので、権限を持つ人が実行する。**

```bash
gcloud run jobs update image-generation-job --region=asia-northeast1 --project=imagen-app-2026 \
  --image=asia-northeast1-docker.pkg.dev/imagen-app-2026/image-repo/imagen-fast-job@sha256:ae0fbf302a87d2c8bbdf2df0524a394cc7302db8282cba7b35e308988f64eeac
```

- 前提: そのダイジェストが Artifact Registry に残っていること（2 節の最後の行は**未確認**）。
- 実行時の環境変数・サービスアカウント・タスク数は、このコマンドでは戻らない。2 節が埋まっていないうちは、戻した結果が成功した実行と同じになる保証は無い。

## 8. 証跡の保存

`docs/image-gen-evidence/` に、秘密とプロンプト本文を除いた確認の出力を、日付つきで置く。**2026-11-02 時点では空**（ジョブの設定・成功した実行の生の出力・ログは、まだ受け取っていない。上の「報告」は要約で、生の出力ではない）。保存する前に、秘密が無いか目で確かめる。
