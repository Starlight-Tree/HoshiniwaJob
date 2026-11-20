#!/usr/bin/env bash
# ログイン（Google）の秘密 3 つを、Infisical に登録する。ユーザーが自分の端末（ホスト）で実行する（エージェントは実行しない・値を見ない）。
#
#   scripts/login-secrets.sh <Infisical のプロジェクト ID> [環境名。既定 dev]
#
# 登録するもの:
#   GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET  Google Cloud Console で作った OAuth クライアントの値（画面に出ない入力で受ける）
#   BETTER_AUTH_SECRET                       その場で作る（openssl rand -base64 32。表示しない）。すでにあれば作り直さない
# 値は、権限 600 の一時ファイルだけに書き、Infisical へ `secrets set --file` で渡す（コマンドの引数・履歴・ログには残さない。終わったら消す）。
#
# BETTER_AUTH_SECRET を作り直さない理由: Better Auth は、これで JWT の署名鍵（DB の auth_jwks）や Google のトークンを暗号化している。
# 変えると、保存済みの鍵が読めなくなり、全員がログアウトされる。変えるのは、理由と影響を確かめてから（手で行う）。
#
# 登録のあとの起動（compose は ${VAR:-} で環境変数を読むので、この形で起動する。素の `docker compose up -d` で作り直すと値が空になる）:
#   infisical run --projectId <プロジェクト ID> --env dev -- docker compose up -d
set -euo pipefail

project="${1:-}"
env_name="${2:-dev}"
if [[ -z "$project" ]]; then
  echo "使い方: $0 <Infisical のプロジェクト ID> [環境名。既定 dev]" >&2
  exit 2
fi
command -v infisical >/dev/null || { echo "infisical コマンドが見つかりません（Infisical CLI を入れて、infisical login してください）。" >&2; exit 2; }
command -v openssl >/dev/null || { echo "openssl が見つかりません。" >&2; exit 2; }

# 安全装置: 対話端末でなければ、何も実行しない（値を read -rs で受けるため。ログや自動実行に値を流さない）
if [[ ! ( -t 0 && -t 1 ) ]]; then
  echo "対話端末ではないので、何も実行しません（infisical は呼んでいません）。あなた自身の端末で実行してください。" >&2
  exit 3
fi

umask 077
tmp="$(mktemp)"
trap 'rm -f "$tmp" "$tmp.err"' EXIT

echo "登録先: Infisical プロジェクト ${project} / 環境 ${env_name} / パス /"

# すでに BETTER_AUTH_SECRET があれば作り直さない（値は /dev/null に捨てる。あるかどうかだけを終了コードで見る）
have_auth_secret=false
if infisical secrets get BETTER_AUTH_SECRET --projectId "$project" --env "$env_name" --path / --plain --silent >/dev/null 2>&1; then
  have_auth_secret=true
fi

read -r -s -p "GOOGLE_CLIENT_ID（入力は表示されません）: " gid
echo
read -r -s -p "GOOGLE_CLIENT_SECRET（入力は表示されません）: " gsec
echo
if [[ -z "$gid" || -z "$gsec" ]]; then
  echo "Client ID と Client Secret の両方が要ります。中止しました。" >&2
  exit 1
fi
case "$gid$gsec" in *[[:space:]]*) echo "値に空白・改行は入れられません。中止しました。" >&2; exit 1 ;; esac
case "$gid" in *.apps.googleusercontent.com) ;; *) echo "注意: Client ID が .apps.googleusercontent.com で終わっていません（貼り間違いではないか確かめてください）。" >&2 ;; esac

{
  printf 'GOOGLE_CLIENT_ID=%s\n' "$gid"
  printf 'GOOGLE_CLIENT_SECRET=%s\n' "$gsec"
  if [[ "$have_auth_secret" == false ]]; then
    printf 'BETTER_AUTH_SECRET=%s\n' "$(openssl rand -base64 32)"
  fi
} >"$tmp"
id_length=${#gid}
secret_length=${#gsec}
unset gid gsec

infisical secrets set --file "$tmp" --projectId "$project" --env "$env_name" --path / --silent >/dev/null 2>"$tmp.err" \
  || { echo "登録に失敗しました（infisical login 済みか、プロジェクトの権限があるかを確かめてください）。" >&2; exit 1; }

# 登録できたことを、キー名と値の有無だけで確かめる（値は表示しない）
exported="$(infisical export --projectId "$project" --env "$env_name" --path / --format=dotenv 2>/dev/null || true)"
missing=()
for key in GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET BETTER_AUTH_SECRET; do
  grep -Eq "^${key}=.+" <<<"$exported" || missing+=("$key")
done
if (( ${#missing[@]} > 0 )); then
  echo "登録したあとの確認で、次のキーが見つかりません: ${missing[*]}（Infisical の画面で確かめてください）。" >&2
  exit 1
fi

echo "登録しました: GOOGLE_CLIENT_ID（${id_length} 文字）、GOOGLE_CLIENT_SECRET（${secret_length} 文字）、BETTER_AUTH_SECRET（$([[ "$have_auth_secret" == true ]] && echo '既存のまま' || echo '新しく作成')）。値は表示していません。"
echo "起動: infisical run --projectId ${project} --env ${env_name} -- docker compose up -d"
