#!/usr/bin/env bash
# Playwright MCP が使う Chromium を取得し、起動を確かめる（コンテナの作成時に postCreateCommand から呼ぶ）。
#
# Chromium に要るシステムのライブラリーとフォントは、イメージに入れてある（.devcontainer/Dockerfile。apt は使わない）。
# 版は @playwright/mcp@0.0.83（user スコープの登録。~/.claude/.claude.json）が依存する playwright の alpha 版に合わせて固定する。
# MCP と同じ版でないと、Chromium のリビジョンが合わない（この版では chromium-1247）。
# 版を上げるときは、Dockerfile のライブラリーの一覧も作り直す（Dockerfile のコメントを参照）。
# ブラウザーは ~/.cache/ms-playwright（名前付きボリューム。イメージには置けない）に入るので、再ビルドしても取得し直さない
# （npx は、取得済みのリビジョンなら何もしない）。
#
# 最後に Chromium を実際に起動して（--version）成功を確かめ、だめなら理由を stderr に出して終了コード 1 で終わる。
# 共有ライブラリーが足りないときも、ここで起動に失敗して分かる（Dockerfile の一覧を確かめる）。
# postCreateCommand の cli-tools は ; で順番に呼ぶので、ここが失敗しても他の確認と導入は続く。
# 失敗してもコンテナは使える（ブラウザー確認ができないだけ）。直したら再実行する: bash .devcontainer/install-playwright.sh
set -uo pipefail

PLAYWRIGHT_VERSION="1.64.0-alpha-1790635538000"
BROWSERS_DIR="$HOME/.cache/ms-playwright"

fail() {
  echo "エラー: Playwright の導入に失敗しました: $1" >&2
  echo "  Playwright MCP のブラウザー確認はできません。直して再実行: bash .devcontainer/install-playwright.sh" >&2
  exit 1
}

install_chromium() {
  # 新規作成直後のボリュームは root 所有で、親の ~/.cache も root 所有で作られることがある
  sudo mkdir -p "$BROWSERS_DIR" &&
    sudo chown "$(id -u):$(id -g)" "$HOME/.cache" &&
    sudo chown -R "$(id -u):$(id -g)" "$BROWSERS_DIR" &&
    PLAYWRIGHT_BROWSERS_PATH="$BROWSERS_DIR" npx -y "playwright@${PLAYWRIGHT_VERSION}" install chromium
}

chromium_path() {
  # 版を固定しているので 1 つだけのはずだが、複数あれば最後（新しい方）を使う
  ls -d "$BROWSERS_DIR"/chromium-*/chrome-linux*/chrome 2>/dev/null | tail -n 1
}

if ! command -v npx >/dev/null 2>&1; then
  fail "npx が見つかりません（node の feature が入っていない可能性があります）"
fi

install_chromium || fail "Chromium の取得に失敗しました（ネットワークまたはボリュームの権限を確認してください）"

chrome="$(chromium_path)"
[ -n "$chrome" ] || fail "Chromium の実行ファイルが見つかりません（$BROWSERS_DIR）"
version="$("$chrome" --version 2>&1)" || fail "Chromium が起動しません（ライブラリーの不足なら .devcontainer/Dockerfile の一覧を確かめる）: $version"

echo "Playwright の Chromium を確認しました（playwright@${PLAYWRIGHT_VERSION}、${version}）。"
