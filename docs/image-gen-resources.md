# 画像生成リソース台帳（正本）

Vertex AI で画像を生成する Cloud Run Job について、**何が・どこに・どの設定でデプロイされ、何が成功したか**の正本。
新しいセッションは、会話の履歴やログを探す前に、この文書を読む。docunavi 側の文書（`docs/image-generation-design.md`）は要点と参照だけを持ち、実設定はここにだけ書く。

- 最終更新: 2026-11-02
- 確認の根拠は、行ごとの「状態」の列に書く。**確認できていないことは「未確認」と書き、確認できた時点でこの表を更新する。**
- 秘密情報（キー・トークン・DB の接続文字列）、資料の本文、機密を含むプロンプトは書かない。

状態の凡例:

| 状態 | 意味 |
|---|---|
| 利用者の報告 | 利用者がコンソールまたは `gcloud` で見て、会話に貼った内容。**生の出力はこのリポジトリに無い**（取得したら `docs/image-gen-evidence/` へ。5 節） |
| ソースで確認 | このリポジトリのコミットを読んだ。**デプロイ済みの設定とは別物**（4 節） |
| 未確認 | まだ誰も見ていない。推測で埋めない |

## 1. 区別すること（混ぜない）

| 軸 | 値 | 備考 |
|---|---|---|
| コードの管理先 | このリポジトリ（`hoshiniwa-job`）の `jobs/image-gen/` | 成功した実行のイメージの元のコードがここにあるかは**未確認**（2 節・4 節） |
| ジョブの配置先（プロジェクト） | `imagen-app-2026` | docunavi の `docunavi-app` とは別。費用の超過が docunavi の停止に波及しないようにしている |
| モデルの呼び出し先（プロジェクト） | `imagen-app-2026` | ジョブの配置先と同じ。利用者の報告 |
| ジョブの配置リージョン | `asia-northeast1` | Cloud Run Job と Artifact Registry の場所 |
| Vertex AI の location | `global` | モデルを呼ぶ場所。ジョブの配置リージョンとは別の概念 |
| デプロイ済みの設定 | 2 節・3 節 | 実際に動いたもの |
| ローカルで提案・変更中の設定 | 4 節 | コミット `3e21bf3` と `ef98041`。**デプロイ済みではない**。プッシュもしていない（`ef98041`） |

## 2. 台帳（デプロイ済みの設定）

| 項目 | 値 | 状態・根拠 |
|---|---|---|
| ジョブ名 | `image-generation-job` | 利用者の報告（2026-11-02） |
| ジョブの配置プロジェクト | `imagen-app-2026` | 利用者の報告 |
| ジョブの配置リージョン | `asia-northeast1` | 利用者の報告 |
| Vertex AI の呼び出し先プロジェクト | `imagen-app-2026` | 利用者の報告 |
| Vertex AI の location | `global` | 利用者の報告 |
| **正確なモデル ID（2026-10-29 の成功した実行）** | `gemini-3.1-flash-lite-image` | **利用者の指示による記録**（2026-11-02）。イメージ内の `/app/main.py` を読んだ出力は、この記録の時点で担当 AI に渡っていない。読めたら、その出力で更新する。**下書き用として最終的に選んだモデルだとは、断定しない**（2 節の下） |
| 呼び出し方式 | **未確認**（`generate_content` か別か） | 同上。独自のエンドポイントがあるかも未確認 |
| イメージ（成功した実行） | `asia-northeast1-docker.pkg.dev/imagen-app-2026/image-repo/imagen-fast-job@sha256:ae0fbf302a87d2c8bbdf2df0524a394cc7302db8282cba7b35e308988f64eeac` | 利用者の報告。ダイジェストで固定。**`latest` などのタグは、成功版の識別情報として使わない** |
| 対応するソースコミット | **未確認** | 4 節。リポジトリのコードをデプロイ元と断定しない |
| 実行サービスアカウント（現在） | `hero-image-job@imagen-app-2026.iam.gserviceaccount.com`。付与した役割は `roles/aiplatform.user` だけ（`editor` なし。キーは作っていない） | 利用者の報告（2026-11-02。手順 1〜3 を利用者が実行し、切り替わったと報告）。生の出力は未受領。担当 AI は IAM を読めず未確認 |
| 実行サービスアカウント（成功した実行・動作確認の実行の時点。復旧用） | 既定の Compute Engine サービスアカウント（`<プロジェクト番号>-compute@developer.gserviceaccount.com`）。`roles/aiplatform.user` と `roles/editor` を持つ | 利用者の報告（2026-11-02）。このアカウントの権限は変えていない（`editor` は残る） |
| 入力方法 | **未確認**（環境変数 `IMAGE_PROMPT` か、引数か） | |
| タスク数・再試行（成功した実行） | `taskCount: 2`、`maxRetries: 1` | 利用者の報告 |
| タスク数・再試行（現在） | `taskCount: 5`、`maxRetries: 0`、並列数は未設定（既定）。1 回の `execute` の生成呼び出しの上限は 5 × (1 + 0) = 5 回。**以前は `taskCount: 1`**（`taskCount` を変えた日時と操作は未確認） | 利用者の報告（2026-11-02 夜。`gcloud run jobs describe` の値を会話に貼った。生の出力は未受領）。担当 AI は読めない |
| Secret Manager（親トークン用） | Secret Manager API は有効。**空の Secret `r2-docunavi-hero-parent` を作成済み**（版なし。値はまだ無い）。誰にも `secretAccessor` を付けない方針 | 利用者の報告（2026-11-02）。担当 AI は読めず未確認。版の有無と IAM の束縛は、保存の前後に利用者が確認する |
| イメージ・環境変数・Secret 参照（現在） | イメージ: `asia-northeast1-docker.pkg.dev/imagen-app-2026/image-repo/docunavi-hero-job@sha256:db1e9cd35528902a02c155c4db3af719306beace40fe432e96486acbbc20ed51`（**2 節の成功した実行の `imagen-fast-job` とは別のイメージ名**）。実行サービスアカウント: `hero-image-job`。環境変数の名前: `GOOGLE_CLOUD_PROJECT`、`GOOGLE_CLOUD_LOCATION`、`R2_BUCKET`、`R2_ACCOUNT_ID`、`R2_TEMP_CREDENTIALS`。うち `R2_TEMP_CREDENTIALS` は **Secret 参照**（Secret `r2-docunavi-hero-write-temp`、版 `latest`）で、ほかは値の直書き。`PLAN_JSON` と `PLAN_SHA256` は**ジョブの定義に無く**、実行時に `--update-env-vars` で渡す | 利用者の報告（2026-11-02 夜。`gcloud run jobs describe` の出力を、名前と数値だけ出す形式で会話に貼った。値は出していない）。このダイジェストが、3.2 の 1 回目の実行のイメージと同じかは**未確認** |
| 出力先・画像の回収方法 | **現在: Cloudflare R2**（バケット `hoshiniwa-images`、prefix `docunavi-hero/<資料 ID>/<plan ハッシュ先頭 16 文字>.png`。名前は `.png` だが中身は JPEG の場合がある。書き込みは `If-None-Match: *` で、既存は上書きしない）。回収は、利用者が読み取り専用の一時キーで取り出す（3.2）。**2026-11-02 の動作確認の実行（3.1）の時点では、コンテナ内のローカルファイルのみで、画像は失われた** | 3.2 の実行で、R2 への保存と回収を利用者が確認（2026-11-02 夜）。生のログは未受領で、`docs/image-gen-evidence/` に無い |
| ジョブの現在の最新の版（generation） | **未確認** | |
| 成功したイメージが Artifact Registry に残っているか | **未確認** | 掃除のルールで消えていないか（`scripts/inspect-image-gen.sh` の手順 5） |

### 2.2 実行身分と費用の扱い（運用ルール）

- 実行身分は、Cloud Run Jobs が API 呼び出しの身分として使う既定の Compute Engine サービスアカウント。**Compute Engine の VM は起動しておらず、VM の費用は発生しない**（利用者の報告）。
- 一方、このアカウントの `roles/editor` は広い。ジョブのコードが誤って、または取り込んだ入力の指示で、他のリソースを変更・削除できてしまう。担当 AI は IAM を変更しない。
- **2026-11-02 に、利用者が専用のサービスアカウント `hero-image-job`（`roles/aiplatform.user` のみ）を作り、ジョブの実行 ID を切り替えた**（利用者の報告）。以後、ジョブは `editor` を持たない。`aiplatform.user` だけで `generate_content`（`global`）が通るかは、実行するまで**未確認**。
  出力先への書き込みは、IAM ではなく R2 の一時キー（`PutObject` / `HeadObject`、`docunavi-hero/`、15〜30 分）で行う。一時キー用の Secret への `secretAccessor` は、その Secret ができた時点で別途付ける（承認制）。親トークンの Secret には、誰にも付けない。
- 動作確認の実行は **1 回だけ**だった（2026-11-02）。以後の実行は、そのつど利用者の承認を得る（初回の R2 保存の試験は `taskCount: 1`、`maxRetries: 0`）。失敗しても自動で再実行しない。
- **1 回の `execute` で起きる生成呼び出しの上限は `taskCount × (1 + maxRetries)`**（成功した実行の設定なら 2 × 2 = 4 回。現在は `taskCount: 5`、`maxRetries: 0` なので 5 回。利用者の報告、2026-11-02 夜）。実行の前に、この回数を利用者に示す。`scripts/inspect-image-gen.sh` がジョブの設定から計算して表示する。
- 実行の前に、出力の回収方法（保存先がコンテナ内だけではないこと）を確認する。確認できないうちは実行しない。
- 結果は「ジョブ成功」と「画像生成 API の成功」と「GCS への保存」を分けて報告する。ジョブ成功だけでは、画像生成の成功とみなさない（ログの API 応答と保存の行、出力先の新しいオブジェクトで確かめる）。

### 2.1 モデルの 3 区分（混ぜない）

| # | 区分 | 値 | 状態 |
|---|---|---|---|
| 1 | 2026-10-29 に成功したモデル | `gemini-3.1-flash-lite-image` | 利用者の指示による記録。イメージ内のコードでの確認は**未** |
| 2 | その後に、下書き用（安いモデル）として選んだモデル | **特定できていない** | 利用者の記憶はあるが、記録が見つかっていない。下の「調べた範囲」 |
| 3 | 現在デプロイされているモデル | **未確認** | ジョブの現在のイメージのダイジェストを、まだ読んでいない。成功した実行のダイジェストと同じかも未確認 |

**2 の調べた範囲（2026-11-02。見つからなかったことは、存在しない証拠ではない）:**

- 星庭ジョブのリポジトリの全コミット・全ブランチ（コミットメッセージ、`jobs/` `frontend/scripts/` `docs/` の差分の中のモデル名）、追跡中のファイル全体、スタッシュ・タグ（無し）。
  モデル名として現れるのは `gemini-nano-banana-2.1`（`frontend/scripts/generate-images/`。2026-10-27 の初出から変更なし。API キーの経路）と `gemini-3.1-flash-lite-image`（`jobs/image-gen/main.py`。`3e21bf3` が初出）の 2 つだけ。
  下書き用・本番用の切り替え設定、別名のジョブ、モデルを変えたコミットは無い。
- docunavi のリポジトリと記憶: 同じ。
- 担当 AI の会話ログ（開発コンテナ内。2026-10-31 20:32 に作り直されたため、**それ以降の 14 本だけ**。うち 1 本はこの会話）: 該当する議論は無い。
  10-29 の成功の前後の会話、星庭ジョブ側の会話ログは、このコンテナに無い。
- Mac のバックアップ（`/tm`、深さ 7 まで）に `.claude` と星庭ジョブのフォルダーは見つからなかった。
- 名前に `fast` / `lite` が付くこと（イメージ名 `imagen-fast-job`、モデル名 `…-lite-image`）だけでは、「安い下書き用」の根拠にしない。
  Nano Banana 2 Lite の公式価格（Gemini API の料金ページ。台帳の範囲外）は docunavi の設計メモにあるが、`gemini-nano-banana-2.1` との価格の比較は取っていない。

**2 と 3 を確かめる手順（利用者が実行。読み取りのみ）:** `scripts/inspect-image-gen.sh` の「ジョブの現在の定義」と「リポジトリのイメージ一覧」。
一覧に、成功した実行より後に作られたイメージ（またはタグ）があれば、その `/app/main.py` を `--read-source` で読む。

## 3. 成功した実行（記録）

実行 ID: `image-generation-job-fjtcv`、成功日時: 2026-10-29 13:41 UTC。結果の出どころはすべて「利用者の報告」で、生の出力は未受領。

| 段階 | 結果 | 根拠 |
|---|---|---|
| デプロイした | 実行時のイメージは上のダイジェスト。いつ・どのコマンドでデプロイしたかは**未確認** | 利用者の報告 |
| 実行した | 実行一覧で 2/2 タスクが完了 | 利用者の報告 |
| 画像生成に成功した | 両タスクのログに画像保存の行と `exit(0)` | 利用者の報告 |
| 画像を保存・回収できた | **未確認**。ログに出たファイル名は `output_task0_0.png` と `output_task1_0.png`（`3e21bf3` の命名と同じ形。ただし、同じコードだという証拠ではない） | 利用者の報告 |
| 画面に表示できた | **まだ**。docunavi のヒーローのカルーセルへの反映は、これから | |

### 3.1 動作確認の実行（2026-11-02、1 回）

利用者が実行し、ログを確認した結果の報告。**実行 ID と生のログは未受領**（`docs/image-gen-evidence/` に無い。受け取ったら置く）。

| 区分 | 結果 |
|---|---|
| ジョブ成功 | 成功 |
| 画像生成 API の成功 | 2 回とも成功 |
| 保存先 | コンテナ内のローカルファイル |
| GCS へのアップロード | 無し |
| 画像の回収 | **できない**（ジョブ終了後に失われる） |

この実行では画像を回収できない。追加の実行はしない（利用者の指示）。現行ジョブは「画像生成 API を呼べる」ことだけが確認できた状態。
GCS 保存の実装・デプロイ、バケットの作成、IAM の変更は、別途承認を得てから行う。

「デプロイした」「実行した」「生成に成功した」「保存・回収できた」「画面に表示できた」は別々に記録する。1 つが済んだことを、次が済んだことにしない。

### 3.2 R2 へ保存した実行（2026-11-02）

結果の出どころは「利用者の報告」と、担当 AI が R2 から取り出して見た画像。実行 ID と生のログは**未受領**（`docs/image-gen-evidence/` に無い）。

| 回 | 内容 | 結果 |
|---|---|---|
| 1 回目（ヒーロー 1 枚） | docunavi の資料 4 の画像。実行 ID は `image-generation-job-z6fgz`（担当 AI の記憶メモにあった値。生の出力は未受領）。R2 のオブジェクトは `docunavi-hero/4/1179505c52d20892.png` | 保存に成功。docunavi の DB に取り込み、承認し、本番に表示された |
| 2 回目（5 枚） | 資料 1・2・3・5・6。`plan.json` は 5 件、`max_images: 5`、モデル `gemini-3.1-flash-lite-image`、16:9。plan の SHA-256 先頭は `3200171cc78f8b84` | 利用者の報告: ジョブ成功、5 枚すべてが R2 に保存、エラーなし、生成呼び出しは 5 回。取り出したファイルの大きさは、ログと一致。先頭バイトは 5 枚とも JPEG |

2 回目の画像は、利用者が読み取り専用の一時キーで取り出し、担当 AI が目で確かめた（文字・数字・ロゴ・顔は見当たらない。資料 2 と 6 には額縁のような縁がある）。その後、docunavi の DB に draft で取り込み、承認した（資料 1・2・3・5・6 すべて。画像 ID 3〜7）。

**実行の手順（利用者がホストで行う。担当 AI は行わない）**

1. 親の鍵（Secret `r2-docunavi-hero-parent` の JSON）を標準入力に流し、`scripts/issue-r2-temp-credentials.py --kind write`（`--ttl 1200`）で、書き込み用の一時キーをローカルで署名する。
2. 一時キーを、Secret `r2-docunavi-hero-write-temp` の**新しい版**として追加する（ジョブは `latest` を参照する。環境変数の文字列での上書きは、定義が Secret 参照なので拒否される）。
3. `gcloud run jobs execute image-generation-job --wait --update-env-vars` で、`PLAN_JSON` と `PLAN_SHA256` を渡して実行する。
4. 終了時に、追加した版を破棄する（失敗しても破棄する）。

取り出しは、`--kind read`（`--ttl 900`）で署名した一時キーを、使い捨てのコンテナ（`python:3.13-slim` と `boto3`）に環境変数で渡して行う。

- 1 回の `execute` の生成呼び出しの上限は `taskCount × (1 + maxRetries)`＝5 回。実行の前に、題材・枚数・費用の扱いを利用者に示し、承認を得た。
- 保存済みの資料は、再実行しても生成を呼ばない（保存の有無を先に確かめる）。
- **未確認:** 1 枚あたりの単価と請求額、実行 ID、一時キーの版が破棄されたことの確認出力、`taskCount` を 5 にした操作。

## 4. ローカルのコミットとの関係（デプロイ済みと混ぜない）

| コミット | 日時 | 内容 | デプロイ |
|---|---|---|---|
| `3e21bf3` | 2026-10-31 | `jobs/image-gen/` の最初のコミット。モデル `gemini-3.1-flash-lite-image`、`vertexai=True`、プロジェクトの既定 `imagen-app-2026`、場所の既定 `global`、縦横比 1:1、出力はコンテナ内のファイルだけ | **未確認**（成功した実行は 10-29 で、このコミットより前） |
| `ef98041` | 2026-11-01 | 承認済みの `plan.json`（GCS）を読み、PNG を GCS へ書く版。`MODEL` は環境変数にする予定 | **push 済み**（`origin/main` に含まれる。確認: `git branch -r --contains ef98041`）。当時の利用者の指示は「プッシュしない」で、食い違っている。いつ・誰の操作で push されたかは未確認。デプロイは**していない**（現在のジョブは R2 版。GCS 版をデプロイした記録は無い） |
| R2 版（この台帳と同じコミット） | 2026-11-02 | `ef98041` の GCS を、Cloudflare R2（S3 互換 API、`boto3==1.40.76`）に書き換えた版。既存バケット `hoshiniwa-images` の `docunavi-hero/<資料ID>/<plan ハッシュ先頭 16 文字>.png` に、`If-None-Match: *` で書く。偽の S3・偽の genai のテスト 23 件が通る（実 API・実 R2・通信なし）。モデルは `gemini-3.1-flash-lite-image` のまま（モデルの決定は保留中） | **デプロイ済みと読める（利用者の報告に基づく）**。現在のジョブ（`docunavi-hero-job`、`R2_TEMP_CREDENTIALS` を Secret 参照）は、この版だけが読む環境変数を使い、3.2 の実行で R2 への保存と回収を確認した。**ただし、ビルド元のコミットが無かった**（この版は未コミットで、デプロイしたイメージとこの版が同一かは、イメージ内の `/app/main.py` を読むまで未確認）。412 の応答、`HeadObject` の 404、チェックサム設定を個別に確かめた記録は未受領 |

**保存先の決定（利用者、2026-11-02）:** R2 が正規で、GCS は使わない。既存バケット `hoshiniwa-images`、prefix `docunavi-hero/`、バケットロックなし、r2.dev は使わない。
ジョブには親トークンを渡さず、親から署名した一時キー（書き込み用: `PutObject` + `HeadObject`、取得用: `GetObject` + `HeadObject`。どちらも `docunavi-hero/`、15〜30 分）だけを渡す。
親トークンの方針（利用者、2026-11-02 に変更）: **新しい親トークンは作らず、既存の Account API token `hoshiniwa-images-rw`（`hoshiniwa-images` のみ、期限 2027-04-27、IP 制限なし、2026-10-27 発行）を親にする。**
当初案の `docunavi-hero-parent-2026-11`（72 時間）は作らない。MCP の一覧に存在しないことを確認済み。
その Access Key ID と Secret Access Key を Secret `r2-docunavi-hero-parent` へ保存する（利用者が端末で行う。値はこの台帳に書かない。保存済みかは、利用者の報告があるまで未確認）。
**既存トークンなので、「作業後に削除」はできない**（削除すると、同じキーを使う既存の求人サイト側が止まる可能性がある）。漏えいの疑いがあるときは、このトークンを再発行（roll）し、既存側のキーも差し替える。

成功した実行（2026-10-29）は、`3e21bf3`（2026-10-31）より前。コンテナのイメージ名（`imagen-fast-job`）もこのリポジトリのパスと一致しない。
したがって、`3e21bf3` は**成功したイメージの元のコードとは限らない**。モデル ID は、イメージ内の `/app/main.py` を読んで確かめる。
既存ジョブを `ef98041` で上書きしない（既存状態の動作確認でなくなる）。

## 5. 確認の手順（読み取り専用）

`scripts/inspect-image-gen.sh`。画像生成・デプロイ・IAM の変更・DB の変更は行わない（使う `gcloud` は `run jobs list/describe`、`run jobs executions list/describe`、`artifacts docker images describe`、`logging read` だけ。
`--read-source` のときだけ `docker pull` と、`--entrypoint` を上書きした `docker run`）。出力は秘密のパターンを伏せ、プロンプトの本文は出さない。
テストは `scripts/test-inspect-image-gen.sh`（偽の `gcloud` と `docker` で確かめる。実際の `gcloud` に対する動作は**未確認**）。

| 誰が | できること |
|---|---|
| 担当 AI | 台帳・スクリプトを読む。スクリプトのテストを実行する。**`imagen-app-2026` は読めない**（日常の ID は閲覧専用で、このプロジェクトの `run.jobs.list` が拒否される。2026-11-02 に確認）。ID の上書きや外しはしない |
| 利用者 | ホストの端末で、自分の権限でスクリプトを実行し、出力を確認してから、`docs/image-gen-evidence/<日付>-inspect.txt` に保存する。台帳の「未確認」を更新する |

```bash
scripts/inspect-image-gen.sh                  # ジョブ・実行・イメージ・ログ（直近の成功した実行）
scripts/inspect-image-gen.sh --read-source    # さらに、そのダイジェストのイメージから /app/main.py を読む（docker が要る）
IMAGEN_EXECUTION=image-generation-job-fjtcv scripts/inspect-image-gen.sh   # 実行を指定
```

### 必要な権限（読み取りだけ）

利用者の権限、または `imagen-app-2026` を読める閲覧用の ID が、次を持つこと。付与は書き込みなので、必要なら利用者が行う。

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

成功した実行のイメージ（2 節のダイジェスト）へ戻す。**書き込みなので利用者が実行する。**

```bash
gcloud run jobs update image-generation-job --region=asia-northeast1 --project=imagen-app-2026 \
  --image=asia-northeast1-docker.pkg.dev/imagen-app-2026/image-repo/imagen-fast-job@sha256:ae0fbf302a87d2c8bbdf2df0524a394cc7302db8282cba7b35e308988f64eeac
```

- 前提: そのダイジェストが Artifact Registry に残っていること（2 節の最後の行は**未確認**）。
- 実行時の環境変数・サービスアカウント・タスク数は、このコマンドでは戻らない。2 節が埋まっていないうちは、戻した結果が成功した実行と同じになる保証は無い。

## 8. 証跡の保存

`docs/image-gen-evidence/` に、秘密とプロンプト本文を除いた確認の出力を、日付つきで置く。**2026-11-02 時点では空**（ジョブの設定・成功した実行の生の出力・ログは、まだ受け取っていない。
上の利用者の報告は、会話にあった要約で、生の出力ではない）。保存する前に、秘密が無いか目で確かめる。
