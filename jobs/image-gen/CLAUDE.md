# jobs/image-gen/（画像生成の Cloud Run Job）

全体の方針・禁止事項は、ルートの [CLAUDE.md](../../CLAUDE.md)。

`main.py` 1 本と `Dockerfile` だけの試作。Vertex AI の `google-genai` で 1 枚を生成し、カレントに `output_task<番号>_<連番>.png` を書く。
環境変数: `GOOGLE_CLOUD_PROJECT` `GOOGLE_CLOUD_LOCATION`（既定 `global`）`CLOUD_RUN_TASK_INDEX` `IMAGE_PROMPT`。

- **実行すると課金される。** 動かさない。動かす必要があるときは、プロンプト・枚数・回数・概算費用を示して承認を得る。
- **テストも CI も無い。** バックエンド・フロントエンドからは参照されていない。デプロイされているかは未確認。
- **以下は今は変えない（保留中）。変えるときは、方針を示して承認を得てから:**
  - Python の版（`Dockerfile` は 3.11。バックエンドは 3.13）
  - モデル名（`gemini-3.1-flash-lite-image`。`frontend/scripts/generate-images/` は `gemini-nano-banana-2.1` で、別の経路〔Gemini の API キー + Batch〕）
  - 既定のプロジェクト ID（コードに書かれている）。プロジェクト ID は登録語の検査（`scripts/check-sensitive-terms.sh`）の対象になりうる
- `requirements.txt` は `google-genai` だけで、版を固定していない。
