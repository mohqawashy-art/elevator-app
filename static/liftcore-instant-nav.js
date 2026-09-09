/* LiftCore — تحميل مسبق خفيف عند المرور على الرابط (لا يعطّل التنقل) */
(function (global) {
  'use strict';

  var SKIP_PATH = /^\/(login|logout|signup|field|platform|onboard|sw\.js|api\/)/i;
  var prefetched = Object.create(null);

  function shouldPrefetch(a) {
    if (!a || !a.href) return false;
    if (a.target === '_blank' || a.hasAttribute('download')) return false;
    if (a.closest('[data-lc-no-instant]')) return false;
    var href = a.getAttribute('href');
    if (!href || href.charAt(0) === '#' || href.indexOf('javascript:') === 0) return false;
    try {
      var u = new URL(href, global.location.origin);
      if (u.origin !== global.location.origin) return false;
      if (SKIP_PATH.test(u.pathname)) return false;
      if (/(?:^|[?&])(popup|print)=1(?:&|$)/.test(u.search)) return false;
      return true;
    } catch (_e) {
      return false;
    }
  }

  function prefetch(href) {
    if (!href) return;
    try {
      var key = new URL(href, global.location.origin).pathname + new URL(href, global.location.origin).search;
      if (prefetched[key]) return;
      prefetched[key] = true;
      var link = document.createElement('link');
      link.rel = 'prefetch';
      link.href = key;
      link.as = 'document';
      document.head.appendChild(link);
    } catch (_e2) { /* ignore */ }
  }

  function bind(root) {
    var selector = '#sidebar a[href], .sidebar a[href], .main a[href], .department-tabs a[href], .department-tab[href]';
    (root || document).querySelectorAll(selector).forEach(function (a) {
      if (a.dataset.lcPrefetchBound) return;
      if (!shouldPrefetch(a)) return;
      a.dataset.lcPrefetchBound = '1';
      a.addEventListener('mouseenter', function () { prefetch(a.getAttribute('href')); }, { passive: true });
      a.addEventListener('focus', function () { prefetch(a.getAttribute('href')); });
      a.addEventListener('touchstart', function () { prefetch(a.getAttribute('href')); }, { passive: true });
    });
  }

  function prefetchNavMenu(limit) {
    var seen = 0;
    var max = limit || 10;
    document.querySelectorAll('#sidebar a[href], .sidebar a[href]').forEach(function (a) {
      if (seen >= max) return;
      if (!shouldPrefetch(a)) return;
      seen += 1;
      prefetch(a.getAttribute('href'));
    });
  }

  function boot() {
    bind();
    prefetchNavMenu(10);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  global.LiftCoreFastNav = { prefetch: prefetch, bind: bind, prefetchNavMenu: prefetchNavMenu };
})(typeof window !== 'undefined' ? window : this);
