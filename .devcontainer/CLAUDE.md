# .devcontainer/（開発コンテナ）

全体の方針・禁止事項は、ルートの [CLAUDE.md](../CLAUDE.md)。

Compose ベース。`devcontainer.json` が、`../docker-compose.yml`（アプリ: `db` `api` `frontend`。ホストの `docker compose up` と共通）に、
`docker-compose.yml`（開発コンテナ `dev` だけ）を重ねて読む。ホストの `docker compose up`（ルートの定義だけ）には `dev` は含まれない。

- **Docker はホストのソケットを渡さず、専用のプロキシ経由。** `docker-proxy/compose.yml`（`wollomatic/socket-proxy`）が、3 つのコンテナの `start` / `stop` / `restart` と読み取りだけを許す。
  `dev` は `DOCKER_HOST=tcp://jobnavi-docker-proxy:2375` で接続し、ネットワーク `jobnavi-dev` にだけ繋ぐ（`api` と `db` には直接届かない）。許可を広げない。
- **資格情報は、プロジェクト専用のボリュームに置く**（`jobnavi-claude-config`・`-infisical-config`・`-gcloud-config`・`-playwright-browsers`。他のプロジェクトと共有しない）。
  別のプロジェクトのボリューム名・マシン ID・サービスアカウントを、ここに足さない。方針と作成の手順は [docs/access-separation.md](../docs/access-separation.md)。
- **MCP は `register-mcp.sh` が user スコープへ「無ければ登録」する**（登録に資格情報は入れない）。足す・変えるときは、必要な権限を先に示して承認を得る。
  gcloud の日常の ID は、閲覧専用のなりすまし（`CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT`。設定済みで、そのサービスアカウントは未作成。状態は `access-separation.md`）。
  書き込みは、既定では実行せず、コマンドを提示してユーザーに実行してもらう。ユーザーが明示して実行を頼んだときだけ、コマンドごとに示して承認を得てから実行する（フックの `ask` の趣旨）。
- **`initializeCommand` はホストで実行される。** `devcontainer.json` を書き換えると、ホスト側の動作が変わる。変更は差分を示して承認を得る。
- **相対パスの基準は、最初の Compose ファイル（`../docker-compose.yml`）のあるリポジトリ直下。** `docker-compose.yml`（このフォルダーの）の `build.context` は `.devcontainer` で、`Dockerfile` もここにある。
- **再ビルドの可能性を壊さない。** ホストの絶対パス・別プロジェクトのファイル・外部のアカウント（GCP のプロジェクト ID など）を足す変更は、先に確認する。再ビルドはホストの作業で、承認なしに実行しない。
- `workspaceFolder` と `dev` のマウントの行き先は `/workspaces/jobnavi`（変更したら、開発コンテナの再作成が要る）。
- Node は feature `node:2` の既定で、バージョンは固定していない（CI・Compose の `frontend` は 24。このコンテナの実測は v26.13.1、2026-11-20）。
- 未コミットの差分があっても、頼まれない限り、触らない・コミットに含めない。
- 見た目の整理用に `local.ui.group` のラベルを付けている（VS Code の Container Tools の表示グループ）。動作には関係しない。
