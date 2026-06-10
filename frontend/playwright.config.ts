import { defineConfig, devices } from '@playwright/test';

const frontendPort = process.env.PLAYWRIGHT_FRONTEND_PORT ?? '5181';
const frontendUrl = `http://127.0.0.1:${frontendPort}`;

export default defineConfig({
  testDir: './e2e',
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR ?? 'test-results',
  timeout: 60_000,
  workers: 1,
  expect: { timeout: 10_000 },
  use: {
    baseURL: frontendUrl,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
    },
    ...devices['Desktop Chrome'],
  },
  webServer: [
    {
      command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8100',
      cwd: '../backend',
      url: 'http://127.0.0.1:8100/api/health',
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
      env: { ...process.env, VITE_API_BASE_URL: '/api' },
      url: frontendUrl,
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
});
