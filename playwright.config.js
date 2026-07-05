// @ts-check
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5002',
    locale: 'ar-SA',
    trace: 'on-first-retry',
  },
  webServer: {
    command: process.platform === 'win32'
      ? 'py scripts/e2e_server.py'
      : 'python3 scripts/e2e_server.py',
    url: 'http://127.0.0.1:5002/login',
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
    env: { E2E_PORT: '5002' },
  },
});
