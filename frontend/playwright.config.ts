import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  // E2E dosyaları tek Mission Core örneğini kullanır; görev state'ini paralel
  // worker'lar arasında paylaşmak gerçek operatör akışını deterministik olmaktan çıkarır.
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    viewport: { width: 1366, height: 768 },
  },
  webServer: [
    {
      command: 'PYTHONPATH=../backend/src python3 -m gokkalkan_backend.operator_http_server --config ../config/runtime/sim.toml --port 8088',
      url: 'http://127.0.0.1:8088/health',
      reuseExistingServer: true,
    },
    {
      command: 'VITE_GOKKALKAN_OPERATOR_API_BASE=http://127.0.0.1:8088 VITE_GOKKALKAN_STAGE2_ROUND_SECONDS=6 npm run dev -- --port 5173',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
    },
  ],
});
