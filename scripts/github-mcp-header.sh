#!/usr/bin/env bash
# GitHub MCP（Actions の起動と監視だけ）へ送る Authorization ヘッダーを、JSON で標準出力に返す。Claude Code の headersHelper から呼ばれる。
# 標準出力は、そのまま Claude Code が読む。端末で実行するとトークンが画面に出るので、手で実行しない（エージェントも実行しない）。
# GitHub App（jobnavi-agent-actions）の秘密鍵から JWT を作り、JobNavi だけの installation トークン（Actions: write / Metadata: read、1 時間）に換える。
# App の ID と秘密鍵（base64）は Infisical（プロジェクトは GITHUB_MCP_PROJECT_ID、環境 prod）から、ログイン済みのユーザーの権限で取る。
# 秘密鍵はファイルに書かない（プロセス置換で渡す）。トークンも書かない。失敗したときは、秘密を含まない理由を標準エラーに出して、非ゼロで終わる。
#
# `--diagnose`: トークンを作らずに、前提（実行ユーザー・Infisical のログイン・秘密の取得）だけを確かめる。標準出力は「OK」の 1 行だけで、秘密は出ない
#   （手で実行してよい。コンテナでは vscode ユーザーで: docker exec -u vscode -e HOME=/home/vscode hoshiniwajob-devcontainer env GITHUB_MCP_PROJECT_ID=<ID> bash /workspaces/hoshiniwajob/scripts/github-mcp-header.sh --diagnose）。
#
# 失敗の原因（標準エラーの先頭の「[原因: …]」で区別する）:
#   1. Infisical のユーザーログインが無い      → コンテナの端末（vscode ユーザー）で `infisical login`
#   2. Claude Code が「Incompatible auth server: does not support dynamic client registration」と出す（OAuth 探索の失敗）
#        → このヘルパーが失敗して、Authorization ヘッダーが渡らなかったときの表示。OAuth のせいではない。`--diagnose` で 1・3・その他の原因を見る
#   3. root で実行された                       → root の HOME にはログインが無い。vscode ユーザーで実行する
set -uo pipefail

DIAGNOSE=0
[ "${1:-}" = "--diagnose" ] && DIAGNOSE=1

OWNER=Starlight-Tree
REPO=JobNavi
API=https://api.github.com

OAUTH_NOTE="（Claude Code に『does not support dynamic client registration』と出ているときは、このヘルパーが失敗してヘッダーが渡らなかった結果です。OAuth の設定は要りません）"
fail() { echo "github-mcp-header: $1" >&2; exit 1; }
fail_cause() { echo "github-mcp-header: [原因: $1] $2 $OAUTH_NOTE" >&2; exit 1; } # $1=原因の名前 $2=対処
err_file=$(mktemp) || fail "一時ファイルを作れません"
trap 'rm -f "$err_file"' EXIT

if [ "$(id -u)" = 0 ]; then
  fail_cause "root で実行された" "root の HOME（${HOME:-?}）には Infisical のログインがありません。vscode ユーザーで実行してください（docker exec -u vscode -e HOME=/home/vscode …）。Claude Code から呼ばれる通常の経路は vscode ユーザーです。"
fi
for c in infisical openssl curl python3; do command -v "$c" >/dev/null 2>&1 || fail "$c が見つかりません"; done
[ -n "${GITHUB_MCP_PROJECT_ID:-}" ] || fail "GITHUB_MCP_PROJECT_ID が設定されていません（headersHelper のコマンドの前に付ける）"

# 標準エラーはファイルに控え、原因の判定にだけ使う（中身は表示しない）
get() { infisical secrets get "$1" --projectId "$GITHUB_MCP_PROJECT_ID" --env prod --plain --silent 2>>"$err_file"; }
infisical_failed() {
  if grep -qiE "logged in|infisical login" "$err_file" 2>/dev/null; then
    fail_cause "Infisical のユーザーログインが無い" "コンテナの端末（vscode ユーザー）で \`infisical login\` を実行してください（ブラウザーでの承認が要ります）。"
  fi
  fail "$1（Infisical のプロジェクト ID・環境 prod・キーの有無・権限を確認。ログインは有効なようです）"
}
app_id=$(get GITHUB_APP_ID) && [ -n "$app_id" ] || infisical_failed "GITHUB_APP_ID を取得できません"
pem_b64=$(get GITHUB_APP_PRIVATE_KEY_B64) && [ -n "$pem_b64" ] || infisical_failed "GITHUB_APP_PRIVATE_KEY_B64 を取得できません"
pem=$(printf %s "$pem_b64" | base64 -d 2>/dev/null) && [ -n "$pem" ] || fail "秘密鍵の base64 を戻せません"

if [ "$DIAGNOSE" = 1 ]; then
  echo "診断: OK（実行ユーザー・Infisical のログイン・App ID と秘密鍵の取得を確認。トークンは作っていません）"
  exit 0
fi

b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }
now=$(date +%s)
header=$(printf '{"alg":"RS256","typ":"JWT"}' | b64url)
payload=$(printf '{"iat":%d,"exp":%d,"iss":"%s"}' $((now - 60)) $((now + 300)) "$app_id" | b64url)
sig=$(printf %s "$header.$payload" | openssl dgst -sha256 -sign <(printf %s "$pem") 2>/dev/null | b64url) && [ -n "$sig" ] || fail "JWT の署名に失敗しました"
jwt="$header.$payload.$sig"

gh_curl() { # $1=認証ヘッダー値 以降=curl の引数（トークンをコマンドラインに出さない）
  local auth=$1; shift
  curl -fsS --max-time 20 -H @<(printf 'Authorization: Bearer %s\n' "$auth") -H 'Accept: application/vnd.github+json' -H 'X-GitHub-Api-Version: 2022-11-28' "$@" 2>/dev/null
}
json_get() { python3 -c 'import sys,json; print(json.load(sys.stdin)[sys.argv[1]])' "$1" 2>/dev/null; }

inst=$(gh_curl "$jwt" "$API/repos/$OWNER/$REPO/installation" | json_get id) && [ -n "$inst" ] || fail "App が $OWNER/$REPO にインストールされていません"
token=$(gh_curl "$jwt" -X POST -d "{\"repositories\":[\"$REPO\"],\"permissions\":{\"actions\":\"write\",\"metadata\":\"read\"}}" "$API/app/installations/$inst/access_tokens" | json_get token) && [ -n "$token" ] || fail "installation トークンを作れません"

printf '{"Authorization":"Bearer %s"}\n' "$token"
