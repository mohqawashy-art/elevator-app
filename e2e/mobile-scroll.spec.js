// @ts-check
const { test, expect } = require('@playwright/test');
const { loginAsAdmin } = require('./helpers');

test.describe('جوال — تمرير الصفحات', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('العملاء والإعدادات قابلة للتمرير', async ({ page }) => {
    await loginAsAdmin(page);

    for (const path of ['/clients', '/settings', '/dashboard']) {
      await page.goto(path);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(700);

      const scrollInfo = await page.evaluate(function () {
        var root = document.documentElement;
        var body = document.body;
        var content = document.querySelector('.main > .content');
        var beforeWin = window.scrollY || root.scrollTop || 0;
        window.scrollTo(0, beforeWin + 320);
        var afterWin = window.scrollY || root.scrollTop || 0;
        var bodyStyle = window.getComputedStyle(body);
        return {
          path: location.pathname,
          mobileClass: root.classList.contains('lc-mobile-scroll'),
          nativeClass: root.classList.contains('lc-mobile-native'),
          frozen: !!(content && content.classList.contains('lc-frozen-layout')),
          bodyOverflowY: bodyStyle.overflowY,
          scrollMoved: afterWin > beforeWin,
          docHeight: Math.max(body.scrollHeight, root.scrollHeight),
          viewHeight: window.innerHeight,
        };
      });

      expect(scrollInfo.mobileClass, JSON.stringify(scrollInfo)).toBe(true);
      expect(scrollInfo.nativeClass, JSON.stringify(scrollInfo)).toBe(true);
      expect(scrollInfo.frozen, JSON.stringify(scrollInfo)).toBe(false);
      expect(
        scrollInfo.bodyOverflowY === 'auto' || scrollInfo.bodyOverflowY === 'visible',
        JSON.stringify(scrollInfo)
      ).toBe(true);
      expect(scrollInfo.docHeight, JSON.stringify(scrollInfo)).toBeGreaterThan(
        scrollInfo.viewHeight
      );
      expect(scrollInfo.scrollMoved, JSON.stringify(scrollInfo)).toBe(true);

      const headerInfo = await page.evaluate(function () {
        var header = document.querySelector('.lc-header, header.lc-header');
        if (!header) return { height: 0 };
        return { height: Math.ceil(header.getBoundingClientRect().height) };
      });
      expect(headerInfo.height, 'header too tall on mobile').toBeLessThan(96);
    }
  });
});
