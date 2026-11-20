#!/usr/bin/env bash
# E2E（表示名の保存）を、使い捨ての Docker スタックの中で流す。ホストに要るのは Docker だけ。リポジトリのルートからでも、どこからでも呼べる。
#   e2e/run.sh
# 毎回、乱数の秘密（Better Auth の署名・DB のパスワード）を作る。ファイルにもログにも出さない（set -x を使わない）。
# 終わったら（失敗しても）、コンテナ・ネットワークを down -v で全部消す。ビルドしたイメージ（jobnavi-e2e-*）は、次回を速くするため残す。
# 失敗時の trace・スクリーンショットは、e2e/test-results（Git 管理外）に出る。終了コードは Playwright のもの。
set -euo pipefail

E2E_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$E2E_DIR")"
cd "$REPO_ROOT"

E2E_BETTER_AUTH_SECRET="$(openssl rand -hex 24)"
E2E_DB_PASSWORD="$(openssl rand -hex 24)"
E2E_ORIGIN="http://web:3000"
export E2E_BETTER_AUTH_SECRET E2E_DB_PASSWORD E2E_ORIGIN

dc() { docker compose -p jobnavi-e2e -f e2e/compose.yml "$@"; }

cleanup() {
  dc down -v --remove-orphans >/dev/null 2>&1 || echo "警告: e2e のスタックを消せませんでした（docker compose -p jobnavi-e2e -f e2e/compose.yml down -v --remove-orphans を手で流してください）" >&2
}
trap cleanup EXIT

mkdir -p e2e/test-results

# run は、イメージがあればビルドし直さない。migrate・seed・e2e（profile tools）も含めて、先に全部ビルドする（コードを変えたあとに古いイメージで流さないため）
dc --profile tools build
dc up -d --wait db
dc run --rm migrate
dc run --rm seed
dc up -d --wait api web

status=0
dc run --rm e2e || status=$?
if [ "$status" -ne 0 ]; then
  echo "E2E が失敗しました（終了コード ${status}）。失敗時の trace・スクリーンショットは e2e/test-results にあります。" >&2
  # 失敗の原因が画面・API 側のときのために、直近のログ（本文に秘密は出ない設計。値は渡していない）を足す
  dc logs --no-color --tail 40 web api >&2 || true
fi
exit "$status"
