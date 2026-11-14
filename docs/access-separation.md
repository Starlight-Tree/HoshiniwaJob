# 権限と資格情報の分離

プロジェクトごとに、資格情報と権限を分ける方針と、その実装の現状です。**状態（2026-11-15）:** 開発コンテナの受け皿（ボリューム・イメージ・スクリプト）は用意済みで、
Infisical・GitHub App・GCP のサービスアカウントの実体は未作成です（作成の手順は「作成の手順」）。再ビルドと接続の確認は未実施です。

## 方針

1. 別のプロジェクト（DocuNavi など）の資格情報・マシン ID・サービスアカウントを、このプロジェクトで再利用しない。
2. Infisical のプロジェクトは、このプロジェクト専用に作る。マシン ID も、このプロジェクト専用に作る。
3. GCP のサービスアカウントも、このプロジェクト専用に作る（運用用プロジェクト `hoshiniwa-job-ops` に置く）。キーは作らない。
4. 秘密は、プロジェクトごとに分けて保管する。
5. 権限は、必要な秘密・リソースだけに絞る（Viewer、閲覧専用、1 リポジトリ限定）。
6. コンテナごとに、必要な秘密だけを読めるようにする（開発コンテナのマシン ID は、開発用の秘密だけ。GitHub App の鍵は別プロジェクトで、ユーザーのログインでだけ読む）。
7. 書き込みは、コマンドごとに明示して、承認を得てから行う。

この方針の本体は、**プロジェクト専用のボリューム**です。認証情報（Claude Code のログイン、MCP の OAuth のトークン）と MCP の登録は、ボリュームの中にあります。
ボリュームを他のプロジェクトと共有すると、方針 1 が破れます（以前は共有していて、DocuNavi 用の MCP の登録が、このプロジェクトからも見えていた）。

## 開発コンテナのボリューム

| ボリューム | 中身 | 作り方 |
|---|---|---|
| `hoshiniwajob-claude-config` | Claude Code の設定・ログイン・履歴・MCP の登録（`~/.claude`） | 作ったあとに `settings.json`・`CLAUDE.md`・履歴だけを写す。認証情報と `.claude.json` は写さない |
| `hoshiniwajob-infisical-config` | Infisical のマシン ID の資格情報（`~/.infisical`。権限 700） | 空で作る |
| `hoshiniwajob-gcloud-config` | gcloud のログイン（`~/.config/gcloud`） | 空で作る |
| `hoshiniwajob-playwright-browsers` | Chromium（`~/.cache/ms-playwright`。キャッシュ） | 空で作る |
| `devcontainer-shared-project-manager` | VS Code の Project Manager の一覧だけ（資格情報なし） | 他のプロジェクトと共有 |

`.devcontainer/docker-compose.yml` が、先頭の 4 つを外部ボリュームとして参照します。起動の前に、ホストで 1 回ずつ作ります。

```bash
for v in claude-config playwright-browsers infisical-config gcloud-config; do docker volume create hoshiniwajob-$v; done
```

## MCP

スコープは、Claude Code の仕様のとおりです（local: そのプロジェクトのパスだけ。project: `.mcp.json`。user: ボリューム内の全プロジェクト）。ボリュームがこのプロジェクト専用なので、
**user スコープに登録しても、他のプロジェクトには見えません。** local は、パスごとの登録で、フォルダーを移すと失われるため使いません。
ボリュームを他のプロジェクトと共有し直すときは、プロジェクト固有の MCP を local に直します。

`.devcontainer/register-mcp.sh` が、コンテナの作成時と起動のたびに、user スコープへ「無ければ登録」します。登録に資格情報は入りません。

| MCP | 資格情報 | 状態 | 備考 |
|---|---|---|---|
| `playwright` | なし（汎用のブラウザー操作） | 登録される | ログイン状態つきの確認が要るときだけ、同名を local で上書きする |
| `infisical` | このプロジェクト専用のマシン ID（`~/.infisical/identity`） | 登録される。マシン ID が無いと起動に失敗する | 使えるツールは `list-secrets`（値は伏せ字）だけ |
| `github` | このプロジェクト専用の GitHub App（1 時間のトークン）。ヘルパー `scripts/github-mcp-header.sh` が作る | `GITHUB_MCP_PROJECT_ID` を指定したときだけ登録される | 対象は `Starlight-Tree/HoshiniwaJob` だけ。`ci.yml` に `workflow_dispatch` は無いので、使えるのは主に監視 |
| `cloudflare` | OAuth（`/mcp` で認可するまで、何もできない） | 登録される | 認可の範囲は、アカウント単位になる見込み（未確認）。R2 の確認が要るときだけ、最小の範囲で認可する |
| `langsmith` | OAuth（同上） | 登録される | このプロジェクトに使う場所は無い。認可しない |
| `prisma` | OAuth（同上） | 登録される | このプロジェクトに使う場所は無い。認可しない |

書き込み系のツールは、`.claude/settings.json` の `ask` で毎回確認になります。

## 現状の対応関係

| 資源 | このプロジェクト専用 | 状態 |
|---|---|---|
| GCP プロジェクト | `hoshiniwa-job-app`（実行用）、`hoshiniwa-job-ops`（運用用） | 作成済み。どちらも空（サービスアカウントも Secret も無い） |
| GCP の閲覧専用サービスアカウント | `hoshiniwajob-viewer@hoshiniwa-job-ops`（なりすまし。`CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT`） | **未作成** |
| Infisical のプロジェクト | `hoshiniwajob`（環境 `dev`）、`hoshiniwajob-github-app`（環境 `prod`。GitHub App の鍵だけ） | **未作成** |
| Infisical のマシン ID | `hoshiniwajob-devcontainer`（`hoshiniwajob` だけの Viewer。`hoshiniwajob-github-app` には入れない） | **未作成** |
| GitHub App | `hoshiniwajob-agent-actions`（`HoshiniwaJob` だけにインストール。`Actions: write`、`Metadata: read`） | **未作成** |
| アプリの秘密（R2 の `STORAGE_S3_*` など） | 今は Git 管理外の `.env`。Infisical の `hoshiniwajob` への移行は未実施 | |

## 作成の手順

作成は、利用者が自分の端末で行います。秘密の値は、画面にも、会話にも、ログにも出しません。

### 1. 再ビルドとログイン

1. 上のボリュームを作る（未作成なら）。VS Code で「Reopen in Container」（初回は、Chromium 用のライブラリーなどで数分）。
2. コンテナのターミナルで、`claude` のログイン（`/login`）、`gcloud auth login --no-launch-browser`。
3. Cloudflare など OAuth の MCP は、必要になったときに `/mcp` から認可する。

### 2. GCP: 閲覧専用のサービスアカウント（`hoshiniwa-job-ops` に置く）

実行前に、各コマンドの内容を確かめてください。API の有効化は、課金の紐づけが要る場合があります。

```bash
OPS_PROJECT=hoshiniwa-job-ops
TARGET_PROJECT=hoshiniwa-job-app
ME=<あなたのアカウント>
SA=hoshiniwajob-viewer@${OPS_PROJECT}.iam.gserviceaccount.com

gcloud services enable iamcredentials.googleapis.com --project "$OPS_PROJECT"
gcloud iam service-accounts create hoshiniwajob-viewer --display-name="HoshiniwaJob viewer" --project "$OPS_PROJECT"
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --member="user:${ME}" --role=roles/iam.serviceAccountTokenCreator --project "$OPS_PROJECT"
for role in roles/cloudbuild.builds.viewer roles/run.viewer roles/logging.viewer roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "$TARGET_PROJECT" \
    --member="serviceAccount:${SA}" --role="$role" --condition=None
done
```

作った直後は、IAM の反映に数分かかります。`does not exist` や `Failed to impersonate` が出たら、待ってやり直してください。サービスアカウントのキーは作りません。

### 3. Infisical: プロジェクトとマシン ID

1. プロジェクト `hoshiniwajob`（環境 `dev`）と、`hoshiniwajob-github-app`（環境 `prod`）を作る。
2. マシン ID `hoshiniwajob-devcontainer` を作る（Universal Auth。Client Secret の有効期限は 30 日）。**`hoshiniwajob` だけに Viewer で追加する。**
3. 資格情報を、コンテナのターミナルで、画面に出さずにボリュームへ置く。

   ```bash
   bash -c 'umask 077; f=$HOME/.infisical/identity; read -rp "Client ID: " i; read -rsp "Client Secret: " s; echo; printf "INFISICAL_UNIVERSAL_AUTH_CLIENT_ID=%s\nINFISICAL_UNIVERSAL_AUTH_CLIENT_SECRET=%s\n" "$i" "$s" > "$f"; unset i s'
   ```

### 4. GitHub App（GitHub MCP を使うとき）

1. GitHub App `hoshiniwajob-agent-actions` を作る。権限は `Actions: Read and write` と `Metadata: Read-only` だけ。`HoshiniwaJob` のリポジトリだけにインストールする。
2. App の ID と秘密鍵（PEM を base64 にしたもの）を、Infisical の `hoshiniwajob-github-app`（環境 `prod`）に、`GITHUB_APP_ID` と `GITHUB_APP_PRIVATE_KEY_B64` として保存する。
   値は CLI の `--file` で渡す（`secrets set KEY=@file` はファイルを読まない）。
3. コンテナのターミナルで `infisical login`（あなたのユーザー。鍵を読むのは、このログインだけ）。
4. `GITHUB_MCP_PROJECT_ID=<プロジェクトの ID> bash scripts/github-mcp-header.sh --diagnose` で、前提を確かめる（標準出力は「OK」の 1 行だけ。トークンは作らない）。
5. `GITHUB_MCP_PROJECT_ID=<プロジェクトの ID> bash .devcontainer/register-mcp.sh github` で登録する（プロジェクトの ID は秘密ではない）。

## 未確認

- ビルドと再ビルド後の動作（Chromium の起動、各 MCP の接続）。
- Cloudflare の OAuth の認可の範囲。
- 無料プランの Infisical で、プロジェクトとマシン ID を追加で作れる数。
