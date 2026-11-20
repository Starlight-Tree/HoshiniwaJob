# 権限と資格情報の分離

プロジェクトごとに、資格情報と権限を分ける方針と、その実装の現状です。**状態（2026-11-15）:** 開発コンテナの受け皿（ボリューム・イメージ・スクリプト）は用意済みで、
Infisical・GitHub App・GCP のサービスアカウントの実体は未作成です（作成の手順は「作成の手順」）。再ビルドと接続の確認は未実施です。

## 方針

1. 別のプロジェクト（DocuNavi など）の資格情報・マシン ID・サービスアカウントを、このプロジェクトで再利用しない。
2. Infisical のプロジェクトは、このプロジェクト専用に作る。マシン ID も、このプロジェクト専用に作る。
3. GCP のサービスアカウントも、このプロジェクト専用に作る（運用用プロジェクト `jobnavi-ops` に置く）。キーは作らない。
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
| `github` | このプロジェクト専用の GitHub App（1 時間のトークン）。ヘルパー `scripts/github-mcp-header.sh` が作る | `GITHUB_MCP_PROJECT_ID` を指定したときだけ登録される | 対象は `Starlight-Tree/JobNavi` だけ。`ci.yml` に `workflow_dispatch` は無いので、使えるのは主に監視 |
| `cloudflare` | OAuth（`/mcp` で認可するまで、何もできない） | 登録される | 認可の範囲は、アカウント単位になる見込み（未確認）。R2 の確認が要るときだけ、最小の範囲で認可する |
| `langsmith` | OAuth（同上） | 登録される | ユーザーが必要なときに使う。OAuth の認可はそのときユーザーが行う。登録と、書き込み系の ask 規則（`.claude/settings.json`）は維持する |
| `prisma` | OAuth（同上） | 登録される | ユーザーが必要なときに使う。OAuth の認可はそのときユーザーが行う。登録と、書き込み系の ask 規則（`.claude/settings.json`）は維持する |

書き込み系のツールは、`.claude/settings.json` の `ask` で毎回確認になります。

## 現状の対応関係

| 資源 | このプロジェクト専用 | 状態 |
|---|---|---|
| GCP プロジェクト | 組織 `dev-cloud`（975415902896）の下。フォルダー `JobNavi`: `jobnavi-app-2026`（実行用。OAuth の同意画面とクライアントもここ）、`jobnavi-ops`（運用用）。フォルダー `GenAI`: `genai-shared-2026`（全アプリ共通の生成 AI。課金あり。Gemini API だけ有効） | 作成済み（2026-11-20）。`jobnavi-app-2026`・`jobnavi-ops` は空（サービスアカウントも Secret も無い）。`genai-shared-2026` に API キー `jobnavi-images`（`generativelanguage` だけに制限）。旧 `hoshiniwa-job-app`・`hoshiniwa-job-ops` は削除予定で、まだ残っている。フォルダーを作るため、組織の IAM に `roles/resourcemanager.folderAdmin` を付けた（外す予定） |
| GCP の閲覧専用サービスアカウント | `jobnavi-viewer@jobnavi-ops`（なりすまし。`CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT`） | **未作成** |
| Infisical のプロジェクト | `jobnavi`（環境 `dev`）、`jobnavi-github-app`（環境 `prod`。GitHub App の鍵だけ） | **未作成** |
| Infisical のマシン ID | `jobnavi-devcontainer`（`jobnavi` だけの Viewer。`jobnavi-github-app` には入れない） | **未作成** |
| GitHub App | `jobnavi-agent-actions`（`JobNavi` だけにインストール。`Actions: write`、`Metadata: read`） | **未作成** |
| アプリの秘密（R2 の `STORAGE_S3_*` など） | 今は Git 管理外の `.env`。Infisical の `jobnavi` への移行は未実施 | |

## 分離済み（docunavi との R2。2026-11-20）

- **docunavi のヒーロー画像用の R2: 2026-11-20 に、専用のバケット `docunavi-hero` に分離した（報告。[台帳](image-gen-resources.md) 3.4）。** 2026-11-02 の決定から、この日まで（実際の開始日は未確認。親の鍵の版 5 の作成は 11-01）は、星庭ジョブのバケット `hoshiniwa-images` の prefix `docunavi-hero/` を共用していた。
  - 今: バケットの共用は、解消した（報告）。docunavi の親トークン `docunavi-hero-parent` の範囲は、`docunavi-hero` だけ（Object Read & Write、期限 2027-05-20）。旧バケット内の存在しないオブジェクト（`docunavi-hero/_nonexistent_probe`）への HEAD は、親の鍵でも、旧バケット向けの write の一時キーでも 403 だった（報告。バケット自体への HEAD ではない。Put・Get・Delete・一覧は未試験。台帳 3.4）。方針 5（権限を絞る）の例外は、docunavi 側の親トークンの範囲については解消したと読めるが、版 5 の件（下の未確認）が分かるまで、言い切れない。ホストは、`hoshiniwa-images` とトークン `hoshiniwa-images-rw` を、星庭ジョブ専用に戻ったものとして扱う。
  - 方針 1（資格情報を再利用しない）の例外が解消したかは、版 5 の件が分かるまで確認できない（下の未確認）。「解消した」とは書かない。
  - 決定（2026-11-20、ユーザー。ホストが依頼文で伝えた）: `hoshiniwa-images-rw` は**失効しない。残す**。理由（決定文）: 範囲は星庭ジョブ自身のバケット `hoshiniwa-images` だけ（分離済み）／版 5 は Secret 側で無効化済み・Secret の IAM は空／失効すると星庭ジョブの利用が止まる。版 5 の持ち主は未確認のまま（推定）。版 5 の鍵は、午後（日付・時刻は原文に無い。回答は 2026-11-20）の確認では R2 で有効だった。トークンを失効しないので、版 5 が `hoshiniwa-images-rw` の鍵なら、R2 では有効なまま残ると推定する（今の有効性は再確認していない。Secret 側の無効化は R2 側の鍵を失効させず、`enable` で戻せる。Secret の IAM が空だったのも午後の確認の時点で、プロジェクト全体の権限による読み取りとアクセスログは未確認）。版 5 の Secret Manager 上の破棄は、決定 1〜3 のどれにも含まれない（ホストの回答 f の「破棄」が何を指すかは未確認）。
  - 経緯: 2026-11-02 の決定では、親に `hoshiniwa-images-rw` を使う設計だった。2026-11-20 に、親は docunavi 専用の `docunavi-hero-parent`（Secret の版 6）に替わり、その後に、バケットを分けた。旧バケットの `docunavi-hero/` にあった 8 件は削除済み（`images/` は残っている）。
  - 影響: `docunavi-hero-parent` の再発行は、docunavi 側の Secret に及ぶ（確認できた範囲。ほかの利用者の有無は未確認）。`hoshiniwa-images-rw` の再発行は、星庭ジョブの `STORAGE_S3_*` に及ぶ。版 5 が `hoshiniwa-images-rw` の鍵なら、その写しも使えなくなる（未確認）。
  - 見直し: 期限の前。先に来るのは `hoshiniwa-images-rw`（画面の表示が 2027-04-28、台帳の記録が 2027-04-27。時差の可能性があるが、理由は未確認。確かめるまで台帳の値は変えない）、次が `docunavi-hero-parent`（2027-05-20）。
  - 未確認: 版 5 の持ち主（`hoshiniwa-images-rw` は推定）。版 5 の鍵が今も R2 で有効か（午後は有効。再確認していない）。版 5 の Secret Manager 上の破棄は、決定に含まれない（回答 f の「破棄」の指す対象は未確認。トークンの失効はしないと決めた）。版 6 の鍵と Cloudflare 側のトークン ID の文字列の突き合わせ（ホストは、動作で、範囲の変更に鍵が追従したことを確認したと報告した。台帳 3.4）。docunavi 側の画像ジョブが版 6 の親を使うこと。read 用の一時キーが prefix の外を読めないこと（write の一時キーでの、prefix の外の Put は 403）。新バケットのバケットロックの有無（作成時に設定せず、画面でも未確認）。旧 `docunavi-hero/` の 8 件が、削除前に `r2.dev` の公開 URL で読めたか（削除済みで確かめられない。docunavi のコードは `hoshiniwa-images` を参照しないと、ホストはコードを読んで回答した。台帳 3.4）。分離後の新バケットでの、画像生成の通し実行。

## 作成の手順

作成は、利用者が自分の端末で行います。秘密の値は、画面にも、会話にも、ログにも出しません。

### 1. 再ビルドとログイン

1. 上のボリュームを作る（未作成なら）。VS Code で「Reopen in Container」（初回は、Chromium 用のライブラリーなどで数分）。
2. コンテナのターミナルで、`claude` のログイン（`/login`）、`gcloud auth login --no-launch-browser`。
3. Cloudflare など OAuth の MCP は、必要になったときに `/mcp` から認可する。

### 2. GCP: 閲覧専用のサービスアカウント（`jobnavi-ops` に置く）

実行前に、各コマンドの内容を確かめてください。API の有効化は、課金の紐づけが要る場合があります。

```bash
OPS_PROJECT=jobnavi-ops
TARGET_PROJECT=jobnavi-app-2026
ME=<あなたのアカウント>
SA=jobnavi-viewer@${OPS_PROJECT}.iam.gserviceaccount.com

gcloud services enable iamcredentials.googleapis.com --project "$OPS_PROJECT"
gcloud iam service-accounts create jobnavi-viewer --display-name="JobNavi viewer" --project "$OPS_PROJECT"
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --member="user:${ME}" --role=roles/iam.serviceAccountTokenCreator --project "$OPS_PROJECT"
for role in roles/cloudbuild.builds.viewer roles/run.viewer roles/logging.viewer roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "$TARGET_PROJECT" \
    --member="serviceAccount:${SA}" --role="$role" --condition=None
done
```

作った直後は、IAM の反映に数分かかります。`does not exist` や `Failed to impersonate` が出たら、待ってやり直してください。サービスアカウントのキーは作りません。

### 3. Infisical: プロジェクトとマシン ID

1. プロジェクト `jobnavi`（環境 `dev`）と、`jobnavi-github-app`（環境 `prod`）を作る。
2. マシン ID `jobnavi-devcontainer` を作る（Universal Auth。Client Secret の有効期限は 30 日）。**`jobnavi` だけに Viewer で追加する。**
3. 資格情報を、コンテナのターミナルで、画面に出さずにボリュームへ置く。

   ```bash
   bash -c 'umask 077; f=$HOME/.infisical/identity; read -rp "Client ID: " i; read -rsp "Client Secret: " s; echo; printf "INFISICAL_UNIVERSAL_AUTH_CLIENT_ID=%s\nINFISICAL_UNIVERSAL_AUTH_CLIENT_SECRET=%s\n" "$i" "$s" > "$f"; unset i s'
   ```

### 4. GitHub App（GitHub MCP を使うとき）

1. GitHub App `jobnavi-agent-actions` を作る。権限は `Actions: Read and write` と `Metadata: Read-only` だけ。`JobNavi` のリポジトリだけにインストールする。
2. App の ID と秘密鍵（PEM を base64 にしたもの）を、Infisical の `jobnavi-github-app`（環境 `prod`）に、`GITHUB_APP_ID` と `GITHUB_APP_PRIVATE_KEY_B64` として保存する。
   値は CLI の `--file` で渡す（`secrets set KEY=@file` はファイルを読まない）。
3. コンテナのターミナルで `infisical login`（あなたのユーザー。鍵を読むのは、このログインだけ）。
4. `GITHUB_MCP_PROJECT_ID=<プロジェクトの ID> bash scripts/github-mcp-header.sh --diagnose` で、前提を確かめる（標準出力は「OK」の 1 行だけ。トークンは作らない）。
5. `GITHUB_MCP_PROJECT_ID=<プロジェクトの ID> bash .devcontainer/register-mcp.sh github` で登録する（プロジェクトの ID は秘密ではない）。

## 未確認

- ビルドと再ビルド後の動作（Chromium の起動、各 MCP の接続）。
- Cloudflare の OAuth の認可の範囲。
- 無料プランの Infisical で、プロジェクトとマシン ID を追加で作れる数。
