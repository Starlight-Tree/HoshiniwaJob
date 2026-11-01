---
paths:
  - "backend/app/migrations/**"
  - "backend/app/migrate.py"
  - "db/**"
---

# マイグレーション・スキーマを触るとき

詳細は [docs/image-storage.md](../../docs/image-storage.md) の「マイグレーション」と、[backend/CLAUDE.md](../../backend/CLAUDE.md)。

- 変更は `backend/app/migrations/NNNN_名前.sql` を新しい番号で足す。適用済みのファイルは書き換えない（sha256 が変わると止まる）
- `DROP` / `TRUNCATE` / リセットを入れない。`recruits.formfile` は、値と使用箇所の確認が済むまで外さない
- `db/schema.sql` と `db/seed_codes.sql` は 0001 の基準。変えたら `baseline_fingerprint.json` と `tests/test_migrate.py` を合わせる
- 適用の前に、DB のバックアップを取る。本番の DB への適用は、操作ごとに承認を得る
- 確認は `python -m app.migrate --status` / `--dry-run` から。テストは `TEST_DATABASE_URL` を付けて実行する（無いとスキップされる）
