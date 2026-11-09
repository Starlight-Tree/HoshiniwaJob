# 開発コンテナのイメージ。Docker の CLI と Compose（docker compose のプラグイン）、curl・ca-certificates、Claude Code CLI（下の層）を足す。Python と Node は devcontainer.json の features が入れる。
# Debian 13 のパッケージで、ソケットもデーモンも含まない。接続先は DOCKER_HOST（./docker-compose.yml）のプロキシだけ。
# Docker-outside-of-Docker の feature は使わない（ホストのソケットを dev にマウントするため）。
FROM mcr.microsoft.com/devcontainers/base:trixie

RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get update -y \
    && apt-get install -y --no-install-recommends docker-cli docker-compose curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && docker --version \
    && docker compose version

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
