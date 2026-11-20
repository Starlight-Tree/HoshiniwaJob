import { defineConfig, devices } from '@playwright/test';

// baseURL は、画面の BETTER_AUTH_URL・API の AUTH_BASE_URL（JWT の iss）と同じ E2E_ORIGIN（compose.yml）
export default defineConfig({
  testDir: './tests',
  outputDir: './test-results',
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_ORIGIN,
    // 失敗したときだけ残す（retries が 0 なので、on-first-retry では残らない）
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 900 } },
    },
  ],
});
