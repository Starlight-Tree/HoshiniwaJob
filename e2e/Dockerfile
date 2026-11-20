# Playwright の実行用。イメージの版（v1.65.1）と package.json の @playwright/test の版は、必ず同じにする
FROM mcr.microsoft.com/playwright:v1.65.1-noble

WORKDIR /e2e

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY tsconfig.json playwright.config.ts ./
COPY support ./support
COPY tests ./tests

CMD ["npx", "playwright", "test"]
