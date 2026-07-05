// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Field portal smoke (K1)', () => {
  test('صفحة دخول الفني', async ({ page }) => {
    await page.goto('/field/login');
    await expect(page).toHaveURL(/\/field\/login/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('محتوى متجاوب على عرض جوال', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/field/login');
    await expect(page.locator('body')).toBeVisible();
  });
});
