/**
 * LiftCore — وضع «عرض فقط»: إخفاء أزرار التعديل مركزياً.
 */
(function (global) {
  'use strict';

  if (global.__LC_CAN_WRITE) return;

  document.documentElement.setAttribute('data-lc-can-write', '0');

  var HIDE_SEL = [
    '.lc-write-only',
    '.lc-admin-delete',
    '.page-actions .btn-primary',
    '.page-actions .btn-success',
    'button[onclick*="openModal"]',
    'button[onclick*="delete"]',
    'button[onclick*="Delete"]',
    'button[onclick*="confirmDelete"]',
    'button[onclick*="addManual"]',
    'a.btn-primary[href*="import"]',
  ].join(',');

  function apply() {
    document.querySelectorAll(HIDE_SEL).forEach(function (el) {
      if (el.classList.contains('lc-read-ok')) return;
      el.classList.add('lc-viewer-hidden');
      el.setAttribute('aria-hidden', 'true');
      if (el.tagName === 'BUTTON' || el.tagName === 'A') {
        el.tabIndex = -1;
      }
    });
    document.querySelectorAll('form[method="post"], form[method="POST"]').forEach(function (form) {
      var action = form.getAttribute('action') || '';
      if (action.indexOf('/settings/') !== -1) return;
      if (form.id === 'loginForm') return;
      form.querySelectorAll('input:not([type="hidden"]), select, textarea, button[type="submit"]').forEach(function (el) {
        el.disabled = true;
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', apply);
  } else {
    apply();
  }
  global.addEventListener('lc-live-sync', apply);
})(window);
