# 開発コンテナのイメージ。Docker の CLI と Compose（docker compose のプラグイン）、curl・ca-certificates、gcloud、Playwright の Chromium に要るライブラリー、
# Infisical CLI、Claude Code CLI（下の層）を足す。Python と Node は devcontainer.json の features が入れる。
# 層の順は、変わりにくいものが上。ツールの版を上げたときに作り直すのは、その層から下だけになる。
# ログイン情報はイメージに含めない（gcloud・Infisical・Claude Code は、それぞれ専用の名前付きボリューム。.devcontainer/docker-compose.yml）。
# Chromium 本体も入れない（ボリューム playwright-browsers に、postCreateCommand の install-playwright.sh が取得する）。
# Debian 13 のパッケージで、ソケットもデーモンも含まない。接続先は DOCKER_HOST（./docker-compose.yml）のプロキシだけ。
# Docker-outside-of-Docker の feature は使わない（ホストのソケットを dev にマウントするため）。
FROM mcr.microsoft.com/devcontainers/base:trixie

RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get update -y \
    && apt-get install -y --no-install-recommends docker-cli docker-compose curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && docker --version \
    && docker compose version

# gcloud（公式の apt リポジトリ。鍵は gpg --dearmor と signed-by で登録する）。MCP の headersHelper は、コンテナの起動の直後に Claude Code が実行するので、
# postCreateCommand ではなくイメージに入れる（導入が間に合わず、gcloud が無いまま失敗するのを避ける）。openssl は GitHub MCP のヘルパー（JWT の署名）が使う。
# Debian のイメージは、取得した .deb を自動で消す設定（docker-clean）を持つ。cache mount に残すため、外す。
RUN rm -f /etc/apt/apt.conf.d/docker-clean \
    && echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    export DEBIAN_FRONTEND=noninteractive \
    && apt-get update -y \
    && apt-get install -y --no-install-recommends apt-transport-https gnupg openssl \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor --yes -o /usr/share/keyrings/cloud.google.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" > /etc/apt/sources.list.d/google-cloud-sdk.list \
    && apt-get update -y \
    && apt-get install -y --no-install-recommends google-cloud-cli \
    && gcloud --version

# Playwright の Chromium に要るライブラリーとフォント（`playwright install-deps chromium` が入れるものと同じ 32 件。debian13 の tools 11 件 + chromium 21 件）。
# 版は install-playwright.sh の PLAYWRIGHT_VERSION（@playwright/mcp@0.0.83 が依存する playwright の alpha 版）に合わせてある。
# 版を上げるときは、この一覧も作り直す。取りこぼしは、postCreateCommand の Chromium の起動確認（--version）で分かる。
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    export DEBIAN_FRONTEND=noninteractive \
    && apt-get update -y \
    && apt-get install -y --no-install-recommends \
        xvfb \
        fonts-noto-color-emoji fonts-unifont xfonts-scalable fonts-liberation fonts-ipafont-gothic \
        fonts-wqy-zenhei fonts-tlwg-loma-otf fonts-freefont-ttf \
        libfontconfig1 libfreetype6 \
        libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 libatspi2.0-0t64 libcairo2 libcups2t64 libdbus-1-3 \
        libdrm2 libgbm1 libglib2.0-0t64 libnspr4 libnss3 libpango-1.0-0 libx11-6 libxcb1 libxcomposite1 \
        libxdamage1 libxext6 libxfixes3 libxkbcommon0 libxrandr2

# Infisical CLI。公式のリリース（GitHub の Infisical/cli）の .deb を、公式の checksums.txt の SHA-256 と照合して入れる（版は v0.44.11）。
# 公式の apt 手順（curl | sudo bash）は、版を固定できないので使わない。ログイン情報（~/.infisical）はイメージに含めない。
# 上げるときは、公開日を確かめてから、版とハッシュを書き換える（arm64 のハッシュだけを固定している）。
ARG INFISICAL_CLI_VERSION=0.44.11
ARG INFISICAL_CLI_SHA256_ARM64=d6998d7ae0c217aa6a9c2a44025dc3df22725c08e1c7fae19dbd60b4ba63505d
RUN --mount=type=cache,target=/var/cache/infisical-cli-dl,sharing=locked \
    set -eu; \
    case "$(uname -m)" in \
      aarch64 | arm64) arch=arm64; expected="${INFISICAL_CLI_SHA256_ARM64}" ;; \
      *) echo "未対応のアーキテクチャです: $(uname -m)（arm64 のハッシュだけを固定している）" >&2; exit 1 ;; \
    esac; \
    deb="infisical_${INFISICAL_CLI_VERSION}_linux_${arch}.deb"; \
    file="/var/cache/infisical-cli-dl/${deb}"; \
    if [ ! -f "${file}" ]; then \
      curl -fsSL -o "${file}.part" "https://github.com/Infisical/cli/releases/download/v${INFISICAL_CLI_VERSION}/${deb}"; \
      mv "${file}.part" "${file}"; \
    fi; \
    if ! echo "${expected}  ${file}" | sha256sum -c -; then \
      rm -f "${file}"; \
      echo "SHA-256 が一致しません。導入を中止します" >&2; \
      exit 1; \
    fi; \
    dpkg -i "${file}"; \
    HOME=/tmp/infisical-build INFISICAL_DISABLE_TELEMETRY=true INFISICAL_DISABLE_UPDATE_CHECK=true infisical --version; \
    rm -rf /tmp/infisical-build

# Claude Code CLI（2026-11-09）。公式の配布物（downloads.claude.ai）を、公式 manifest の SHA-256 と照合して /usr/local/bin に置く。版は 2.1.319（2026-11-05 ビルド）。
# 公式の curl | bash は版を固定できないので使わない。自動更新は無い。上げるときは、版とハッシュを書き換えて再ビルドする（arm64 のハッシュだけを固定している）。
# VS Code 拡張（anthropic.claude-code）の同梱バイナリとは別物。ログイン情報はイメージに含めない。
ARG CLAUDE_CODE_VERSION=2.1.319
ARG CLAUDE_CODE_SHA256_ARM64=a7e687fd1cb054d651c7588223de3786c99d4c682365e3c3ae1e59ce7f3a591f
RUN set -eu; \
    case "$(uname -m)" in \
      aarch64 | arm64) expected="${CLAUDE_CODE_SHA256_ARM64}"; platform=linux-arm64 ;; \
      *) echo "未対応のアーキテクチャです: $(uname -m)（arm64 のハッシュだけを固定している）" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/claude "https://downloads.claude.ai/claude-code-releases/${CLAUDE_CODE_VERSION}/${platform}/claude"; \
    echo "${expected}  /tmp/claude" | sha256sum -c -; \
    install -m 755 /tmp/claude /usr/local/bin/claude; \
    rm -f /tmp/claude; \
    HOME=/tmp/claude-build claude --version; \
    rm -rf /tmp/claude-build
