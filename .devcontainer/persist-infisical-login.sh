#!/usr/bin/env bash
# Infisical CLI のユーザーのログイン状態を、開発コンテナの再ビルド後も残す（利用者が決定）。
# ファイル形式のキーリング（~/infisical-keyring）はボリュームの外にあるので、実体をボリューム（~/.infisical/keyring）へ移し、
# ~/infisical-keyring からの symlink にする。ログイン情報の暗号化のパスフレーズは、同じボリュームの infisical-config.json にあるため、
# ボリュームを読める人には、ログイン状態を使える（保管時の保護ではない）。使い終わったら `infisical logout` で消せる。
# 何度実行しても同じ。失敗してもコンテナの起動は止めない。

set -u
src="$HOME/infisical-keyring"
dst="$HOME/.infisical/keyring"

[ -d "$HOME/.infisical" ] || exit 0

if [ -L "$src" ]; then
  echo "persist-infisical-login: 済み（symlink）。"
elif [ -d "$src" ] && [ ! -e "$dst" ]; then
  cp -a "$src" "$dst" && chmod 700 "$dst" && mv "$src" "$src.bak" && ln -s "$dst" "$src" || { echo "persist-infisical-login: 移動に失敗しました。"; exit 0; }
  if infisical login status >/dev/null 2>&1; then
    rm -rf "$src.bak"
    echo "persist-infisical-login: ログイン状態をボリュームへ移しました。"
  else
    rm -f "$src" && mv "$src.bak" "$src"
    echo "persist-infisical-login: 移した後にログイン状態を確認できなかったため、元に戻しました。"
  fi
elif [ ! -e "$src" ] && [ -d "$dst" ]; then
  ln -s "$dst" "$src" && echo "persist-infisical-login: ボリュームのログイン状態に symlink を張りました。"
else
  echo "persist-infisical-login: 何もしません（$src と $dst の状態が想定外です）。"
fi
exit 0
