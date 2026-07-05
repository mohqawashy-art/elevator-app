// @ts-check
const { test, expect } = require('@playwright/test');
const { loginAsAdmin, collectConsoleErrors } = require('./helpers');

test.describe('LiftCore E2E', () => {
  test('تسجيل الدخول', async ({ page }) => {
    await loginAsAdmin(page);
    await expect(page).toHaveURL(/\/(welcome|dashboard)/);
  });

  test('الصفحات الرئيسية بدون أخطاء Console', async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await loginAsAdmin(page);
    const paths = [
      '/dashboard',
      '/clients',
      '/invoices',
      '/contracts',
      '/reports',
      '/reports/parts-billing',
      '/maintenance-visits',
      '/settings',
    ];
    for (const path of paths) {
      await page.goto(path);
      await page.waitForLoadState('domcontentloaded');
      await expect(page.locator('#h-date, .header-title, .page-title').first()).toBeVisible();
    }
    expect(errors, errors.join('\n')).toEqual([]);
  });

  test('إضافة عميل', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto('/clients');
    page.on('dialog', (d) => d.accept());
    await page.getByRole('button', { name: 'إضافة عميل' }).click();
    await expect(page.locator('#modal-add')).toHaveClass(/open/);
    const unique = `عميل PW ${Date.now()}`;
    await page.locator('#f-name').fill(unique);
    await page.locator('#f-phone').fill('512345679');
    await page.getByRole('button', { name: 'حفظ العميل' }).click();
    await page.waitForURL(/\/clients/);
    await expect(page.getByText(unique)).toBeVisible();
  });

  test('فتح نموذج فاتورة', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto('/invoices');
    await page.getByRole('button', { name: 'إضافة مستند' }).click();
    await expect(page.locator('#modal-add')).toHaveClass(/open/);
    await expect(page.locator('#modal-title')).toContainText('فاتورة');
    await expect(page.locator('#f-desc')).toBeVisible();
    await expect(page.locator('#invtax-input')).toBeVisible();
  });

  test('فتح نموذج زيارة صيانة', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto('/maintenance-visits');
    await page.getByRole('button', { name: 'إضافة زيارة' }).click();
    await expect(page.locator('#modal-add')).toHaveClass(/open/);
    await expect(page.locator('#f-elevator-sel')).toBeVisible();
  });

  test('تقرير قطع الغيار', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto('/reports/parts-billing');
    await expect(page.locator('body[data-report-id="report-parts"]')).toBeVisible();
  });
});
