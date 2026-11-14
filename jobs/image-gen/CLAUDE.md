# jobs/image-gen/（画像生成の Cloud Run Job）

全体の方針・禁止事項は、ルートの [CLAUDE.md](../../CLAUDE.md)。

**デプロイ済みのジョブ（ジョブ名・場所・イメージのダイジェスト・モデル・成功した実行）の正本は [docs/image-gen-resources.md](../../docs/image-gen-resources.md)。**
このフォルダーのコードは、デプロイ済みのイメージの元のコードとは限らない（成功した実行は 2026-10-29、このフォルダーの最初のコミットは 2026-10-31）。
既存のジョブを、ここのコード（`6c01342` を R2 に書き換えたもの）で上書きしない。デプロイ・モデルの変更・保存先の変更をしたら、台帳の更新までが完了条件。

`main.py` 1 本と `Dockerfile` と `test_main.py`。Vertex AI の `google-genai` で、承認済みの plan（環境変数 `PLAN_JSON`）の自分のタスク番号の行（`document_id` `prompt` `aspect_ratio`）から 1 枚を生成し、
**Cloudflare R2**（S3 互換 API、`boto3`）の既存バケットへ `docunavi-hero/<資料ID>/<plan のハッシュ先頭 16 文字>.png` で書く。保存先は R2 が正規で、GCS は使わない（2026-11-02 の決定）。
docunavi の `plan` が作る plan.json を使う（docunavi の `docs/image-generation-design.md`）。
環境変数: `GOOGLE_CLOUD_PROJECT` `GOOGLE_CLOUD_LOCATION`（既定 `global`）`CLOUD_RUN_TASK_INDEX`（任意）。
必須: `PLAN_JSON` `PLAN_SHA256`（`PLAN_JSON` の UTF-8 バイト列の SHA-256）`R2_BUCKET` `R2_ACCOUNT_ID`（32 桁の 16 進）`R2_TEMP_CREDENTIALS`（JSON: `access_key_id` `secret_access_key` `session_token` `expires_at`。`scripts/issue-r2-temp-credentials.py` が作る。残りが 5 分未満なら、生成の前に止まる）。

- **実行すると課金される。** 動かさない。動かす必要があるときは、プロンプト・枚数・回数・概算費用を示して承認を得る。
- **R2 への書き込みの決まり:**
  - ジョブに渡すのは、`PutObject` と `HeadObject` だけを許可し、`docunavi-hero/` に限った一時キー（15〜30 分）。親トークンは渡さない。コードは `put_object` と `head_object` しか呼ばない（削除・一覧は呼ばない）。
  - 先に `head_object` で保存済みか確かめ、あれば生成せずに終わる（終了コード 0）。書き込みは `If-None-Match: *`（412 は「保存済み・上書きしない」として終了コード 0）。既存のオブジェクトを上書きしない。
  - 拡張子は `.png` 固定。`Content-Type` だけを画像のバイト列（PNG / JPEG / WebP）で決める。判定できなければ保存しない。
  - ログはキーとバイト数だけ。署名付き URL・キー・トークンは出さない。DB にはキーも URL も保存しない（docunavi 側の決定）。
  - 別のバケット・prefix（既存の求人サイト画像など）には書かない。`OUTPUT_PREFIX` はコードの定数で、環境変数にしない。
- **plan が止める条件（API を呼ぶ前）:** `PLAN_SHA256` と `PLAN_JSON` の SHA-256 が違う、タスク番号が plan の範囲外、件数が 20 超または `max_images` 超、
  入力が不正（`document_id` は数字のみ、`prompt` は 1000 文字以内、`aspect_ratio` は 1:1 / 16:9 / 4:3 / 3:2）。画像が 0 枚なら終了コード 1。
- **テスト:** `test_main.py`（偽の S3・偽の genai。実 API・実 R2・通信なし）。`pip install -r requirements.txt pytest` の後、このフォルダーで `python -m pytest`。CI には入れていない。
  boto3 の本物のクライアントで、エンドポイント・リージョン `auto`・`If-None-Match: *`・セッショントークン・追加チェックサム無しのヘッダーを、送信直前で止めて確かめる。**実際の R2 に対する動作は未確認**（412 の応答、`HeadObject` の 404、一時キーの権限、`when_required` のチェックサム設定）。
- バックエンド・フロントエンドからは参照されていない。**このコードがデプロイされているかは未確認**（デプロイ済みのジョブは別のイメージで動いた実績がある。台帳）。`PLAN_JSON` の環境変数の大きさの上限は未確認（1 件の plan なら小さい）。
- **以下は今は変えない（保留中）。変えるときは、方針を示して承認を得てから:**
  - Python の版（`Dockerfile` は 3.11。バックエンドは 3.13）
  - モデル名（`gemini-3.1-flash-lite-image`。`frontend/scripts/generate-images/` は `gemini-nano-banana-2.1` で、別の経路〔Gemini の API キー + Batch〕）
  - 既定のプロジェクト ID（コードに書かれている）。プロジェクト ID は登録語の検査（`scripts/check-sensitive-terms.sh`）の対象になりうる
- `requirements.txt` は `google-genai==2.30.1` と `boto3==1.40.76` に固定（実モデル・実 R2 での動作は未確認。`google-cloud-storage` は外した）。
