// @ts-check

/** @param {import('@playwright/test').Page} page */
async function loginAsAdmin(page) {
  await page.goto('/login');
  await page.locator('#user').fill('admin');
  await page.locator('#pass').fill('E2ePass123!');
  await page.locator('#loginBtn').click();
  await page.waitForURL(/\/(welcome|dashboard)/);
}

/** @param {import('@playwright/test').Page} page */
function collectConsoleErrors(page) {
  /** @type {string[]} */
  const errors = [];
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    const text = msg.text();
    if (/google maps|gm_authFailure|favicon|Failed to load resource|net::ERR_|googleapis\.com|gstatic\.com/i.test(text)) return;
    errors.push(text);
  });
  page.on('pageerror', (err) => {
    errors.push(err.message);
  });
  return errors;
}

module.exports = { loginAsAdmin, collectConsoleErrors };
