# E2E 用の画面（frontend/ を next build して next start）。ビルド context は ../frontend（compose.yml）。
# 除外するもの（.env 系・node_modules など）は、このファイルの隣の web.Dockerfile.dockerignore（BuildKit が、Dockerfile の名前 + .dockerignore として読む）。
FROM node:24-slim

ENV NEXT_TELEMETRY_DISABLED=1

# next.config.ts が、ビルド時に読む（rewrites・images.remotePatterns）。実行時の環境変数だけでは足りない
ARG API_BASE_URL=http://api:8000
ARG IMAGE_PUBLIC_BASE_URL=/media
ENV API_BASE_URL=${API_BASE_URL} \
    IMAGE_PUBLIC_BASE_URL=${IMAGE_PUBLIC_BASE_URL}

WORKDIR /app
RUN chown node:node /app
USER node

COPY --chown=node:node package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY --chown=node:node . .
RUN npm run build

EXPOSE 3000
CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
