#!/usr/bin/env bash
# このプロジェクトの MCP を、user スコープ（~/.claude/.claude.json。専用ボリューム hoshiniwajob-claude-config）に登録する。
# 何度実行しても同じ（登録済みなら何もしない）。コンテナの作成時（postCreateCommand）と起動のたびに（postStartCommand）呼ばれる。
#
# ・ボリュームがこのプロジェクト専用なので、user スコープでも他のプロジェクトには見えない（docs/access-separation.md）。
# ・登録に資格情報は入れない。Infisical はマシン ID（~/.infisical/identity）、GitHub は専用のヘルパーが、起動時に読む。
#   Cloudflare・LangSmith・Prisma は、/mcp で認可するまで何もできない（認可は利用者が行う。許可の範囲は最小にする）。
# ・登録するのは、名前を指定しなければ次の 6 つ。GitHub は、環境変数 GITHUB_MCP_PROJECT_ID（Infisical の GitHub App 用プロジェクトの ID。秘密ではない）が
#   あるときだけ登録する（無ければ飛ばす）。
#     playwright infisical cloudflare langsmith prisma github
# ・使い方: bash .devcontainer/register-mcp.sh [名前...]
#     GitHub だけを後から登録する: GITHUB_MCP_PROJECT_ID=<ID> bash .devcontainer/register-mcp.sh github
# ・失敗してもコンテナの作成・起動は止めない（終了コードは常に 0）。

set -u
cd "$(dirname "$0")/.." || exit 0
ROOT="$(pwd)"

claude_bin="$(command -v claude || true)"
if [ -z "$claude_bin" ]; then
  echo "register-mcp: claude が見つかりません（イメージの Claude Code CLI が入っていません）。" >&2
  exit 0
fi

# $1=名前、以降=`claude mcp add --scope user` に渡す引数
add() {
  local name=$1
  shift
  if "$claude_bin" mcp get "$name" >/dev/null 2>&1; then
    echo "register-mcp: $name は登録済みです。"
    return
  fi
  if "$claude_bin" mcp add --scope user "$@" >/dev/null; then
    echo "register-mcp: $name を登録しました。新しいセッションから使えます。"
  else
    echo "register-mcp: $name の登録に失敗しました。" >&2
  fi
}

register_github() {
  local id="${GITHUB_MCP_PROJECT_ID:-}"
  if [ -z "$id" ]; then
    echo "register-mcp: github は飛ばしました（GITHUB_MCP_PROJECT_ID が無い）。"
    return
  fi
  case "$id" in
    *[!0-9a-fA-F-]*)
      echo "register-mcp: github は飛ばしました（GITHUB_MCP_PROJECT_ID の形が違う）。" >&2
      return
      ;;
  esac
  if "$claude_bin" mcp get github >/dev/null 2>&1; then
    echo "register-mcp: github は登録済みです。"
    return
  fi
  local json
  json=$(printf '{"type":"http","url":"https://api.githubcopilot.com/mcp/x/actions","headersHelper":"GITHUB_MCP_PROJECT_ID=%s bash %s/scripts/github-mcp-header.sh"}' "$id" "$ROOT")
  if "$claude_bin" mcp add-json --scope user github "$json" >/dev/null; then
    echo "register-mcp: github を登録しました。新しいセッションから使えます。"
  else
    echo "register-mcp: github の登録に失敗しました。" >&2
  fi
}

register_one() {
  case "$1" in
    playwright) add playwright playwright -- npx -y @playwright/mcp@0.0.83 --headless --browser chromium --isolated ;;
    infisical) add infisical infisical -- bash "$ROOT/.devcontainer/infisical-mcp.sh" ;;
    cloudflare) add cloudflare --transport http cloudflare https://mcp.cloudflare.com/mcp ;;
    langsmith) add langsmith --transport http langsmith https://apac.api.smith.langchain.com/mcp ;;
    prisma) add prisma --transport http prisma https://mcp.prisma.io/mcp ;;
    github) register_github ;;
    *) echo "register-mcp: 知らない名前です: $1" >&2 ;;
  esac
}

if [ "$#" -eq 0 ]; then
  set -- playwright infisical cloudflare langsmith prisma github
fi
for n in "$@"; do
  register_one "$n"
done
exit 0
