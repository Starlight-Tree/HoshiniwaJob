# 開発コンテナのイメージ。Docker の CLI と Compose（docker compose のプラグイン）だけを足す。
# Debian 13 のパッケージで、ソケットもデーモンも含まない。接続先は DOCKER_HOST（./docker-compose.yml）のプロキシだけ。
# Docker-outside-of-Docker の feature は使わない（ホストのソケットを dev にマウントするため）。
FROM mcr.microsoft.com/devcontainers/base:trixie

RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get update -y \
    && apt-get install -y --no-install-recommends docker-cli docker-compose \
    && rm -rf /var/lib/apt/lists/* \
    && docker --version \
    && docker compose version
