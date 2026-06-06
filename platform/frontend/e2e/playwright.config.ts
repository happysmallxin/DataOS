/**
 * Playwright E2E 测试配置 — DataOS 前后端联调.
 *
 * 前提:
 *   1. 后端运行在 http://localhost:8001
 *   2. 前端运行在 http://localhost:5000 (Vite dev) 或本文件直接测后端 API
 *
 * 策略: E2E 测试直接调用后端 API (比走浏览器 UI 更快更稳定),
 *       关键 UI 流程用浏览器测试.
 */
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 30000,
  retries: 1,
  workers: 1, // 串行执行, 避免测试间数据冲突
  reporter: [['list'], ['html', { outputFolder: 'playwright-report' }]],

  use: {
    baseURL: 'http://localhost:8001',
    extraHTTPHeaders: {
      'Content-Type': 'application/json',
    },
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'api-tests',
      testMatch: '**/*.spec.ts',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
