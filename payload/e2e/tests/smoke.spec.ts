import { test, expect } from '@playwright/test'

/**
 * Smoke: アプリが起動しログイン画面またはトップに到達できること。
 * BASE_URL 未起動時は skip。
 */
test.describe('smoke', () => {
  test('root responds', async ({ page }) => {
    const response = await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 15_000 })
    test.skip(!response, 'BASE_URL unreachable — start frontend or set BASE_URL in e2e/.env')

    expect(response!.status()).toBeLessThan(500)
    await expect(page.locator('body')).toBeVisible()
  })
})
