# jobs/image-gen/（画像生成の Cloud Run Job）

全体の方針・禁止事項は、ルートの [CLAUDE.md](../../CLAUDE.md)。

**デプロイ済みのジョブ（ジョブ名・場所・イメージのダイジェスト・モデル・成功した実行）の正本は [docs/image-gen-resources.md](../../docs/image-gen-resources.md)。**
このフォルダーのコードは、デプロイ済みのイメージの元のコードとは限らない（成功した実行は 2026-10-29、このフォルダーの最初のコミットは 2026-10-31）。
既存のジョブを、ここのコード（`ef98041`）で上書きしない。デプロイ・モデルの変更・保存先の変更をしたら、台帳の更新までが完了条件。

`main.py` 1 本と `Dockerfile` だけ。Vertex AI の `google-genai` で、承認済みの `plan.json`（GCS）の自分のタスク番号の行（`document_id` `prompt` `aspect_ratio`）から 1 枚を生成し、
`OUTPUT_GCS_PREFIX/<資料ID>/<plan のハッシュ先頭 16 文字>.png` へ書く。docunavi の `plan` が作る plan.json を使う（docunavi の `docs/image-generation-design.md`）。
環境変数: `GOOGLE_CLOUD_PROJECT` `GOOGLE_CLOUD_LOCATION`（既定 `global`）`CLOUD_RUN_TASK_INDEX` `PLAN_GCS_URI` `PLAN_SHA256` `OUTPUT_GCS_PREFIX`（後ろの 3 つは必須）。

- **実行すると課金される。** 動かさない。動かす必要があるときは、プロンプト・枚数・回数・概算費用を示して承認を得る。
- **plan が止める条件（API を呼ぶ前）:** `PLAN_SHA256` と plan.json の SHA-256 が違う、タスク番号が plan の範囲外、件数が 20 超または `max_images` 超、
  入力が不正（`document_id` は数字のみ、`prompt` は 1000 文字以内、`aspect_ratio` は 1:1 / 16:9 / 4:3 / 3:2）。画像が 0 枚なら終了コード 1。ログは資料 ID・バイト数・保存先だけ。
- **テストも CI も無い**（偽のクライアントでの確認は 2026-11-01 に実行したが、リポジトリには入れていない）。バックエンド・フロントエンドからは参照されていない。**このコードがデプロイされているかは未確認**（デプロイ済みのジョブは別のイメージで動いた実績がある。台帳）。
- **以下は今は変えない（保留中）。変えるときは、方針を示して承認を得てから:**
  - Python の版（`Dockerfile` は 3.11。バックエンドは 3.13）
  - モデル名（`gemini-3.1-flash-lite-image`。`frontend/scripts/generate-images/` は `gemini-nano-banana-2.1` で、別の経路〔Gemini の API キー + Batch〕）
  - 既定のプロジェクト ID（コードに書かれている）。プロジェクト ID は登録語の検査（`scripts/check-sensitive-terms.sh`）の対象になりうる
- `requirements.txt` は `google-genai==2.30.1` と `google-cloud-storage==3.15.1` に固定（実モデルでの動作は未確認）。
