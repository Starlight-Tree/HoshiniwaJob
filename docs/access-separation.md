# 権限と資格情報の分離

プロジェクトごとに、資格情報と権限を分ける方針と、その実装の現状です。**状態（2026-11-20）:** 開発コンテナの受け皿（ボリューム・イメージ・スクリプト）は用意済みです。Infisical のプロジェクト `jobnavi` は作成済みです（下の表）。
Infisical のマシン ID・GitHub App・GCP のサービスアカウントの実体は未作成です（作成の手順は「作成の手順」）。再ビルドと接続の確認は未実施です。
Infisical の権限と資格情報について、公式文書で確認したことと、確認できていないことは「Infisical の権限と資格情報」。

## 方針

1. 別のプロジェクト（DocuNavi など）の資格情報・マシン ID・サービスアカウントを、このプロジェクトで再利用しない。
2. Infisical のプロジェクトは、このプロジェクト専用に作る。マシン ID も、このプロジェクト専用に作る。
3. GCP のサービスアカウントも、このプロジェクト専用に作る（運用用プロジェクト `jobnavi-ops` に置く）。キーは作らない。
4. 秘密は、プロジェクトごとに分けて保管する。
5. 権限は、必要な環境・パス・秘密・リソースだけに絞る（閲覧専用、1 リポジトリ限定）。Infisical の Viewer は「プロジェクト全体の読み取り専用」で、環境やパスでは絞れない（文書の文言からの導出）。値も読めるものとして扱う（「Infisical の権限と資格情報」）。
6. コンテナごとに、必要な秘密だけを読めるようにする（開発コンテナのマシン ID は、開発用の秘密だけ。GitHub App の鍵は別プロジェクトで、ユーザーのログインでだけ読む）。
   ただし、コンテナにユーザーのログインが残っていると、専用のマシン ID に絞っても、届く範囲は、そのユーザーの範囲になりうる（推定。「Infisical の権限と資格情報」）。このコンテナは、ユーザーのログインを再ビルド後も残す設計（`.devcontainer/persist-infisical-login.sh`）で、コンテナの端末でのユーザーのログインと、専用のマシン ID で絞ることは、同時には成り立たない恐れがある（推定）。未解決。
7. 書き込みは、コマンドごとに明示して、承認を得てから行う。

この方針の本体は、**プロジェクト専用のボリューム**です。認証情報（Claude Code のログイン、MCP の OAuth のトークン）と MCP の登録は、ボリュームの中にあります。
ボリュームを他のプロジェクトと共有すると、方針 1 が破れます（以前は共有していて、DocuNavi 用の MCP の登録が、このプロジェクトからも見えていた）。

## 開発コンテナのボリューム

| ボリューム | 中身 | 作り方 |
|---|---|---|
| `hoshiniwajob-claude-config` | Claude Code の設定・ログイン・履歴・MCP の登録（`~/.claude`） | 作ったあとに `settings.json`・`CLAUDE.md`・履歴だけを写す。認証情報と `.claude.json` は写さない |
| `hoshiniwajob-infisical-config` | Infisical のマシン ID の資格情報と、ユーザーのログイン状態（`~/.infisical`。権限 700）。ログイン状態は、`.devcontainer/persist-infisical-login.sh` が起動のたびにここへ移す（暗号化のパスフレーズも同じボリューム。ソースで確認。動かした結果は未確認） | 空で作る |
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
| `infisical` | このプロジェクト専用のマシン ID（`~/.infisical/identity`） | 登録される。マシン ID が無いと起動に失敗する | 起動スクリプトが、ツールを `list-secrets` だけにし、値を伏せ字にする設定を入れている（`.devcontainer/infisical-mcp.sh`）。効くかは未確認（固定している版 0.0.25 がこの 2 つの設定を持つか。持たなければ、既定の全ツール・値つきになる）。この限定と伏せ字は設定で、権限ではない（MCP 自体は権限を持たず、届く範囲はマシン ID の権限で決まる） |
| `github` | このプロジェクト専用の GitHub App（1 時間のトークン）。ヘルパー `scripts/github-mcp-header.sh` が作る | `GITHUB_MCP_PROJECT_ID` を指定したときだけ登録される | 対象は `Starlight-Tree/JobNavi` だけ。`ci.yml` に `workflow_dispatch` は無いので、使えるのは主に監視 |
| `cloudflare` | OAuth（`/mcp` で認可するまで、何もできない） | 登録される | 認可の範囲は、アカウント単位になる見込み（未確認）。R2 の確認が要るときだけ、最小の範囲で認可する |
| `langsmith` | OAuth（同上） | 登録される | ユーザーが必要なときに使う。OAuth の認可はそのときユーザーが行う。登録と、書き込み系の ask 規則（`.claude/settings.json`）は維持する |
| `prisma` | OAuth（同上） | 登録される | ユーザーが必要なときに使う。OAuth の認可はそのときユーザーが行う。登録と、書き込み系の ask 規則（`.claude/settings.json`）は維持する |

書き込み系のツールは、`.claude/settings.json` の `ask` で毎回確認になります。

## 現状の対応関係

| 資源 | このプロジェクト専用 | 状態 |
|---|---|---|
| GCP プロジェクト | 組織 `dev-cloud`（975415902896）の下。フォルダー `JobNavi`: `jobnavi-app-2026`（実行用。OAuth の同意画面とクライアントもここ）、`jobnavi-ops`（運用用）。フォルダー `GenAI`: `genai-shared-2026`（全アプリ共通の生成 AI。課金あり。Gemini API だけ有効） | 作成済み（2026-11-20）。`jobnavi-app-2026`・`jobnavi-ops` は空（サービスアカウントも Secret も無い）。`genai-shared-2026` に API キー `jobnavi-images`（`generativelanguage` だけに制限）。旧 `hoshiniwa-job-app`・`hoshiniwa-job-ops` は 2026-11-20 に削除した（空で、Gemini の呼び出しは直近 14 日で 0 件。30 日以内なら `gcloud projects undelete` で戻せる）。フォルダーを作るため、組織の IAM に `roles/resourcemanager.folderAdmin` を付けた（外す予定） |
| GCP の閲覧専用サービスアカウント | `jobnavi-viewer@jobnavi-ops`（なりすまし。`CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT`） | **未作成** |
| Infisical のプロジェクト | `jobnavi`（使うのは環境 `dev`）、`jobnavi-github-app`（環境 `prod`。GitHub App の鍵だけ） | `jobnavi`: 作成済み（2026-11-20。コンテナのユーザーのログインで `infisical sm projects create`。ID `5851ffe9-3b94-40d0-8ac1-b9ea0e8708cb`、スラッグ `jobnavi-lk3q`。環境は dev・staging・prod が既定で付いた。報告。作成時の出力）。`jobnavi-github-app`: **未作成** |
| Infisical のマシン ID | `jobnavi-devcontainer`（`jobnavi` だけに追加。`jobnavi-github-app` には入れない。権限は開発用の秘密だけに絞る。Viewer は環境・パスで絞れない） | **未作成** |
| GitHub App | `jobnavi-agent-actions`（`JobNavi` だけにインストール。`Actions: write`、`Metadata: read`） | **未作成** |
| アプリの秘密（R2 の `STORAGE_S3_*` など） | 今は Git 管理外の `.env`。Infisical の `jobnavi` への移行は未実施 | ログインの 3 つ（`GOOGLE_CLIENT_ID`・`GOOGLE_CLIENT_SECRET`・`BETTER_AUTH_SECRET`）だけは、2026-11-20 に `jobnavi` の `dev` へ登録した（`scripts/login-secrets.sh`。報告。名前と文字数だけ確認。値は見ていない） |

## 分離済み（docunavi との R2。2026-11-20）

- **docunavi のヒーロー画像用の R2: 2026-11-20 に、専用のバケット `docunavi-hero` に分離した（報告。[台帳](image-gen-resources.md) 3.4）。** 2026-11-02 の決定から、この日まで（実際の開始日は未確認。親の鍵の版 5 の作成は 11-01）は、星庭ジョブのバケット `hoshiniwa-images` の prefix `docunavi-hero/` を共用していた。
  - 今: バケットの共用は、解消した（報告）。docunavi の親トークン `docunavi-hero-parent` の範囲は、`docunavi-hero` だけ（Object Read & Write、期限 2027-05-20）。旧バケット内の存在しないオブジェクト（`docunavi-hero/_nonexistent_probe`）への HEAD は、親の鍵でも、旧バケット向けの write の一時キーでも 403 だった（報告。バケット自体への HEAD ではない。Put・Get・Delete・一覧は未試験。台帳 3.4）。方針 5（権限を絞る）の例外は、docunavi 側の親トークンの範囲については解消したと読めるが、版 5 の件（下の未確認）が分かるまで、言い切れない。ホストは、`hoshiniwa-images` とトークン `hoshiniwa-images-rw` を、星庭ジョブ専用に戻ったものとして扱う。
  - 方針 1（資格情報を再利用しない）の例外が解消したかは、版 5 の件が分かるまで確認できない（下の未確認）。「解消した」とは書かない。
  - 決定（2026-11-20、ユーザー。ホストが依頼文で伝えた）: `hoshiniwa-images-rw` は**失効しない。残す**。理由（決定文）: 範囲は星庭ジョブ自身のバケット `hoshiniwa-images` だけ（分離済み）／版 5 は Secret 側で無効化済み・Secret の IAM は空／失効すると星庭ジョブの利用が止まる。版 5 の持ち主は未確認のまま（推定）。版 5 の鍵は、午後（日付・時刻は原文に無い。回答は 2026-11-20）の確認では R2 で有効だった。トークンを失効しないので、版 5 が `hoshiniwa-images-rw` の鍵なら、R2 では有効なまま残ると推定する（今の有効性は再確認していない。Secret 側の無効化は R2 側の鍵を失効させず、`enable` で戻せる。Secret の IAM が空だったのも午後の確認の時点で、プロジェクト全体の権限による読み取りとアクセスログは未確認）。版 5 の Secret Manager 上の破棄は、決定 1〜3 のどれにも含まれない（ホストの回答 f の「破棄」が何を指すかは未確認）。
  - 経緯: 2026-11-02 の決定では、親に `hoshiniwa-images-rw` を使う設計だった。2026-11-20 に、親は docunavi 専用の `docunavi-hero-parent`（Secret の版 6）に替わり、その後に、バケットを分けた。旧バケットの `docunavi-hero/` にあった 8 件は削除済み（`images/` は残っている）。
  - 影響: `docunavi-hero-parent` の再発行は、docunavi 側の Secret に及ぶ（確認できた範囲。ほかの利用者の有無は未確認）。`hoshiniwa-images-rw` の再発行は、星庭ジョブの `STORAGE_S3_*` に及ぶ。版 5 が `hoshiniwa-images-rw` の鍵なら、その写しも使えなくなる（未確認）。
  - 見直し: 期限の前。先に来るのは `hoshiniwa-images-rw`（画面の表示が 2027-04-28、台帳の記録が 2027-04-27。時差の可能性があるが、理由は未確認。確かめるまで台帳の値は変えない）、次が `docunavi-hero-parent`（2027-05-20）。
  - 未確認: 版 5 の持ち主（`hoshiniwa-images-rw` は推定）。版 5 の鍵が今も R2 で有効か（午後は有効。再確認していない）。版 5 の Secret Manager 上の破棄は、決定に含まれない（回答 f の「破棄」の指す対象は未確認。トークンの失効はしないと決めた）。版 6 の鍵と Cloudflare 側のトークン ID の文字列の突き合わせ（ホストは、動作で、範囲の変更に鍵が追従したことを確認したと報告した。台帳 3.4）。docunavi 側の画像ジョブが版 6 の親を使うこと。read 用の一時キーが prefix の外を読めないこと（write の一時キーでの、prefix の外の Put は 403）。新バケットのバケットロックの有無（作成時に設定せず、画面でも未確認）。旧 `docunavi-hero/` の 8 件が、削除前に `r2.dev` の公開 URL で読めたか（削除済みで確かめられない。docunavi のコードは `hoshiniwa-images` を参照しないと、ホストはコードを読んで回答した。台帳 3.4）。分離後の新バケットでの、画像生成の通し実行。

## Infisical の権限と資格情報（公式文書で確認。2026-11-20）

出典は、公式文書の元ファイル（GitHub `Infisical/infisical` の `main`。2026-11-20 時点のコミット `178d46972c`。生の MDX を curl で取得）。読んだ主なページ（`docs/` 以下）: `documentation/platform/identities/universal-auth.mdx`・`machine-identities.mdx`、`documentation/platform/access-controls/role-based-access-controls.mdx`・`folder-rbac.mdx`・`additional-privileges.mdx`、`documentation/platform/organization.mdx`、`documentation/platform/agent-vault/`（`how-it-works.mdx`・`plan-your-setup.mdx` など）、`documentation/platform/pam/ai-agents/unattended.mdx`、`cli/reference.mdx`・`cli/usage.mdx`、`internals/permissions/project-permissions.mdx`。
調査担当 4 人が、引用を原文と照合し、別の担当が、挙げられた主張 226 件を再照合した（「引用が主張を支えない」とされた 2 件は、ここで使っていない）。メインの会話では、取得した 9 ページ（作業用の写しで、リポジトリには無い）から、主な引用 14 件を原文と照合した（全件一致）。それ以外の主張は、調査担当の照合に拠り、メインでは再照合していない。
**文書に書いてあることの確認で、この環境の Infisical で動かした確認ではない（実機は未確認）。** 文書が書いていないことは「未確認」と書く。この節の「報告」は、コンテナの Claude が、ユーザーの指示で見て伝えた内容を含む（台帳の凡例の「運用者が見て報告」より、出どころが 1 段広い。生の出力はリポジトリに無い）。

### Client Secret と、アクセストークンの寿命（別の設定）

- Client Secret の TTL の既定は 0 で、無期限。使用回数の既定も 0 で、無制限。どちらも、Client Secret ごとに作成時に決める（API の TTL の上限は 315360000 秒）。計画の「30 日」は、最初の方針文書（コミット `82426f4`）の作成の手順に書かれた値で、作成時に入れるもの。自動ではない。決めた日と理由は、記録が見つかっていない（未確認）。
- 有効期限の通知は、TTL が 0 の Client Secret を無視する。確認は 1 日 1 回で、1 日未満の寿命は見逃しうる。数日以上の TTL に使う。
- アクセストークン（Client ID と Client Secret でログインして得るトークン）の TTL と Max TTL の既定は、2592000 秒（30 日）と書かれている（Universal Auth のページの設定の一覧、machine-identities のページ）。**同じ Universal Auth のページの別の箇所には「既定は 7200 秒」ともあり、文書が食い違う。** 作った ID の設定画面で、実際の値を確かめる（未確認）。Access Token Period を設定すると、更新を続ける限り期限の無いトークンになる。
- 信頼する IP による制限は、有料機能（Cloud は Pro）。既定は 0.0.0.0/0（制限なし）。

### 権限の粒度

- `describeSecret`（名前・メタデータ）と `readValue`（値）は、別の権限。値を読むには両方が要る。古い `read` は、この 2 つの合計（legacy）。どちらも、条件 `environment`・`secretPath`・`secretName`・`secretTags` で絞れる。
- 組み込みの Viewer は「プロジェクト内のすべての資源の読み取り専用」（文書の文言）。「環境・パスでは絞れない」は、文書の文言ではなく、ここからの導出（Viewer の個別の権限と条件が、文書に無い）。**文書は、Viewer が持つ個別の権限（値を読めるか）を載せていない（未確認）。** 読めるものとして扱う。読める秘密は、強い資格情報になりうる。
- 絞るには、No Access（権限なし）に、Additional Privileges（個人・マシン ID ごとの権限。環境・パスの条件つき）を足すか、カスタムロールを使う。**カスタムロールは Enterprise プラン**（組み込みの 4 つは全プラン）。Additional Privileges に必要なプランは、見つかっていない（未確認）。
- 複数のロールを付けた ID は、すべてのロールの権限の合計を得る（共通部分ではない）。フォルダー単位のアクセス制御（Pro）は、そのフォルダーの中で、プロジェクトのロールを置き換える（広げることも、狭めることもある）。
- マシン ID が届くのは、追加されたプロジェクトだけ（プロジェクト専用の ID は、そのプロジェクトだけ。組織の ID は、追加された各プロジェクト）。なお、人の側には、組織の管理者が、全プロジェクトの一覧から「Join as Admin」で自分を管理者として加えられる経路と、assume privilege の権限を持つ人が、最大 1 時間、ID の権限を引き継げる経路がある。

### ユーザーのログインと、専用のマシン ID

- 報告（コンテナの Claude、2026-11-20）: コンテナのユーザーのログイン（ブラウザー認証）で、プロジェクトの一覧に 8 件（`docunavi-prod` など、他のプロジェクトを含む）が見えた。中身は見ていない。登録が済んだので `infisical logout` を推奨した（実行したかは未確認。今のログイン状態は見ていない）。
- 公式文書: `infisical login` の既定は、ユーザーのログイン。資格情報は、OS のキーリングか、ファイルの保管庫（`~/infisical-keyring` と `~/.infisical/infisical-config.json`）に置かれる。ユーザーのログインで見えるのは、そのユーザーが入っているプロジェクト。`INFISICAL_TOKEN` などのトークンは、保存済みのログインより優先される。マシン ID だけを使う（保存済みのログインを無視する）設定は、文書に見つかっていない（未確認）。保存済みのログインを消す方法は `infisical logout`（`--local-only` は、サーバー側のセッションを失効させない）。
- 公式文書: 自分のコンピューターでエージェントを動かすなら、コンテナか VM に隔離することを勧める。隔離しないと、エージェントは自分のユーザーとして、ファイルと Infisical CLI のログインを使える（Agent Vault の文書）。敏感な作業は、ほかの資格情報の無い専用のホストかコンテナで、マシン ID を使って動かすことを勧める（PAM の文書）。
- ソースで確認（このリポジトリ。動かしてはいない）: `.claude/hooks/guard-deploy-cli.py` は、`infisical run` と `infisical user` を、確認なしで通す（`INFISICAL_SAFE_FIRST`。冒頭の説明は「値を表示しない」）。`infisical run -- <コマンド>` は、秘密を環境変数に入れて任意のコマンドを動かすので、ログインが残っていれば、確認なしで、値を使うコマンドを動かせると読める（推定）。
- **推定（文書が直接は述べていない）: 専用のマシン ID の権限を絞っても、コンテナにユーザーのログインが残る限り、エージェントの届く範囲は、そのユーザーの範囲になりうる。** 絞るには、①マシン ID の権限を絞る、②ほかの経路（ユーザーのログイン、トークン）を取り除く、の両方が要る。「構造的に絞られる」とは言わない。
- 未解決: GitHub App の鍵を「コンテナのユーザーのログインでだけ読む」（方針 6、作成の手順 4）は、上の推定と両立しない恐れがある。この環境は、ユーザーのログインを再ビルド後も残す設計（`persist-infisical-login.sh`。利用者が決定。使い終わったら `infisical logout` で消せる）なので、「ログインが残る限り」の前提は、この環境で成り立ちうる。読んだらすぐ `infisical logout` する、ログインをコンテナの外で行う、などの運用は、ユーザーが決める。

### MCP と Agent Vault

- 秘密を扱える公式の MCP（`@infisical/mcp`）は、公式文書のサイトではなく、リポジトリの README だけが説明している。既定は、全ツールを出し、値も返す。値の伏せ字（`INFISICAL_MASK_SECRET_VALUES`）とツールの限定（`INFISICAL_ENABLED_TOOLS`）は、任意の設定。MCP 自体は権限を持たないので、マシン ID の範囲を絞ることが前提。伏せ字のときは、Describe Secret だけで足りる。この環境は、起動スクリプトが両方を設定する。ただし、固定している版（0.0.25）がこの 2 つの設定を持つかは、未確認（README は `main` の 0.1.0 のもの。どの版で入ったかは見つかっていない）。
- Agent Vault は、AI エージェントに本物の資格情報を渡さず、プロキシが付ける別の製品。旧 Agent Proxy は非推奨で、Agent Vault に置き換わる。このプロジェクトは、Agent Vault を使っていない（採用するかは未決）。使うときの注意（文書）: セッションを作る側のマシン ID の資格情報は、エージェントの環境に置かない。その ID が持つ範囲で、エージェントが自分に権限を足せるため。セッションのトークンが漏れると、期限か失効まで、同じ権限を使われる。

## 作成の手順

作成は、利用者が行います（`jobnavi` は、利用者の指示で、コンテナの Claude が、コンテナのユーザーのログインから作成した。「現状の対応関係」）。秘密の値は、画面にも、会話にも、ログにも出しません。

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

1. プロジェクト `jobnavi`（環境 `dev`）は作成済み（「現状の対応関係」）。`jobnavi-github-app`（環境 `prod`）は、まだ作っていない（手順 4 で使う）。
2. マシン ID `jobnavi-devcontainer` を作る（Universal Auth）。Client Secret の TTL は、作成時に決める。**30 日は、このプロジェクトの計画値で、自動の設定ではない**（公式の既定は 0 で、無期限）。アクセストークンの寿命は、別の設定（「Infisical の権限と資格情報」）。
   **`jobnavi` だけに追加し、権限は、開発用の秘密だけを読む範囲に絞る。** Viewer は、プロジェクト全体の読み取りなので、これだけでは絞れない（絞り方は未決）。
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
- 作るマシン ID の、アクセストークンの TTL の実際の値（文書は 30 日と 7200 秒の両方を書いている）。
- 組み込みの Viewer が値を読めるか。Additional Privileges に必要なプラン。
- マシン ID だけを使い、保存済みのユーザーのログインを無視する設定が、CLI にあるか（見つかっていない）。
- 固定している `@infisical/mcp@0.0.25` が、値の伏せ字とツールの限定の設定を持つか。
- 今のコンテナで、Infisical にユーザーとしてログインしているか（`infisical logout` を実行したか。見ていない）。
- 公式文書は `main`（2026-11-20）、コンテナの CLI は v0.44.11 に固定（`.devcontainer/Dockerfile:49`）。この節の CLI の挙動（`INFISICAL_TOKEN` の優先順位・`logout --local-only`・`sm projects create`）が、その版で同じか。`main` の文書は、2026-11-04 に `infisical sm` を `infisical secrets-manager` へ改名している（GitHub のコミットの説明で確認）。現行の CLI での名前は未確認。「現状の対応関係」の `sm projects create` は、v0.44.11 で動いたもの。
