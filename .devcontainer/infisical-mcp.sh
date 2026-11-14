#!/usr/bin/env bash
# Infisical 公式 MCP（@infisical/mcp）の起動用。Claude Code の user スコープの登録（register-infisical-mcp.sh）が、このスクリプトを呼ぶ。
# 資格情報（Universal Auth の Client ID / Secret）は ~/.infisical/identity（ボリューム内・権限 600）から読み、
# 登録（~/.claude/.claude.json）には入れない。Client Secret を発行し直しても、登録はそのまま使える。
# ・秘密の値は MCP の応答でマスクする（INFISICAL_MASK_SECRET_VALUES=true）。
# ・使えるツールは、秘密の一覧（list-secrets。値は伏せ字）だけ。
#   秘密の値を MCP 経由で入れると、値がエージェントの会話を通る。値の登録は CLI で行う（docs/access-separation.md の「Infisical」）。
# ・MCP にはプロジェクトを絞る設定が無い。届く範囲は、この ID（hoshiniwajob-devcontainer）が入っているプロジェクトで決まる。
# ・標準出力は MCP の通信に使われる。診断は標準エラーに出す。

set -euo pipefail

# 失敗の原因は、標準エラーの先頭の「[原因: …]」で区別する。
#   root で実行された        → root の HOME（/root）には資格情報が無く、起動に失敗して「CONNECTION_CLOSED」になる。vscode ユーザーで実行する
#   資格情報（identity）が無い → マシン ID の資格情報を置く（docs/access-separation.md の「Infisical」）
if [ "$(id -u)" = 0 ]; then
  echo "infisical-mcp: [原因: root で実行された] root の HOME（${HOME:-?}）にはマシン ID の資格情報がありません。vscode ユーザーで実行してください（docker exec -u vscode -e HOME=/home/vscode …）。Claude Code から呼ばれる通常の経路は vscode ユーザーです。" >&2
  exit 1
fi

identity="$HOME/.infisical/identity"
if [ ! -r "$identity" ]; then
  echo "infisical-mcp: [原因: 資格情報が無い] $identity がありません。マシン ID の資格情報を置いてください（docs/access-separation.md の「Infisical」）。" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$identity"
set +a

export INFISICAL_AUTH_METHOD=universal-auth
export INFISICAL_MASK_SECRET_VALUES=true
export INFISICAL_ENABLED_TOOLS=list-secrets

exec npx -y @infisical/mcp@0.0.25
