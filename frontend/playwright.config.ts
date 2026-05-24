import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    viewport: { width: 1366, height: 768 },
  },
  webServer: {
    command: 'VITE_GOKKALKAN_STAGE2_ROUND_SECONDS=6 npm run dev -- --port 5173',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: true,
  },
});
