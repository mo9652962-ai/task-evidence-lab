import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  timeout: 30_000,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure', ...devices['Desktop Chrome'] },
  webServer: [
    { command: '.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765', cwd: '../backend', url: 'http://127.0.0.1:8765/api/health', reuseExistingServer: true, timeout: 30_000 },
    { command: 'npm run dev -- --host 127.0.0.1', cwd: '.', url: 'http://127.0.0.1:5173', reuseExistingServer: true, timeout: 30_000 },
  ],
})
