/* LiftCore — تحميل مسبق للصفحات + انتقال سريع (بدون وميض أسود) */
(function (global) {
  'use strict';

  var CACHE = 'liftcore-nav-prefetch-v1';
  var SKIP_PATH = /^\/(login|logout|signup|field|platform|onboard|sw\.js|api\/)/i;
  var prefetched = Object.create(null);
  var inflight = Object.create(null);

  function hasAdminShell() {
    return !!(document.getElementById('sidebar') && document.querySelector('.main'));
  }

  function normalizeUrl(href) {
    try {
      var u = new URL(href, global.location.origin);
      return u.pathname + u.search;
    } catch (_e) {
      return '';
    }
  }

  function shouldHandle(a, e) {
    if (!hasAdminShell()) return false;
    if (!a || !a.href) return false;
    if (a.target === '_blank' || a.hasAttribute('download')) return false;
    if (e && (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)) return false;
    if (a.closest('[data-lc-no-instant]')) return false;
    if (a.hasAttribute('data-lc-open-tab') || a.classList.contains('lc-open-tab')) return false;
    if (a.hasAttribute('data-lc-back') || a.classList.contains('lc-back-link')) return false;
    var href = a.getAttribute('href');
    if (!href || href.charAt(0) === '#' || href.indexOf('javascript:') === 0) return false;
    try {
      var u = new URL(href, global.location.origin);
      if (u.origin !== global.location.origin) return false;
      if (SKIP_PATH.test(u.pathname)) return false;
      if (/(?:^|[?&])(popup|print)=1(?:&|$)/.test(u.search)) return false;
      return true;
    } catch (_e2) {
      return false;
    }
  }

  function openCache() {
    if (!global.caches) return Promise.resolve(null);
    return global.caches.open(CACHE);
  }

  function prefetch(url) {
    var key = normalizeUrl(url);
    if (!key || prefetched[key] || inflight[key]) return inflight[key] || Promise.resolve();
    inflight[key] = openCache().then(function (cache) {
      if (!cache) return;
      return cache.match(key).then(function (hit) {
        if (hit) {
          prefetched[key] = true;
          return;
        }
        return global.fetch(key, {
          credentials: 'same-origin',
          headers: { Accept: 'text/html', 'X-LiftCore-Prefetch': '1' },
        }).then(function (res) {
          if (!res || !res.ok) return;
          prefetched[key] = true;
          return cache.put(key, res.clone());
        }).catch(function () { /* ignore */ });
      });
    }).finally(function () {
      delete inflight[key];
    });
    return inflight[key];
  }

  function go(url) {
    var key = normalizeUrl(url);
    if (!key) return;
    document.documentElement.classList.add('lc-nav-pending');
    var nav = function () {
      global.location.href = key;
    };
    var pending = inflight[key] || prefetch(key);
    Promise.resolve(pending).then(nav).catch(nav);
  }

  function bindFastNavLinks(root) {
    (root || document).querySelectorAll('a[href]').forEach(function (a) {
      if (a.dataset.lcFastNavBound) return;
      if (!shouldHandle(a)) return;
      a.dataset.lcFastNavBound = '1';
      a.addEventListener('mouseenter', function () { prefetch(a.getAttribute('href')); });
      a.addEventListener('focus', function () { prefetch(a.getAttribute('href')); });
      a.addEventListener('touchstart', function () { prefetch(a.getAttribute('href')); }, { passive: true });
      a.addEventListener('click', function (e) {
        if (!shouldHandle(a, e)) return;
        e.preventDefault();
        go(a.getAttribute('href'));
      });
    });
  }

  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[href]');
    if (!a || a.dataset.lcFastNavBound) return;
    if (!shouldHandle(a, e)) return;
    e.preventDefault();
    go(a.getAttribute('href'));
  });

  document.addEventListener('DOMContentLoaded', function () {
    bindFastNavLinks();
    document.querySelectorAll('#sidebar .nav-item[href], .sidebar .nav-item[href], #sidebar .nav-item-single[href], .sidebar .nav-item-single[href]').forEach(function (a) {
      prefetch(a.getAttribute('href'));
    });
  });

  if (document.readyState !== 'loading') bindFastNavLinks();

  global.LiftCoreFastNav = { prefetch: prefetch, go: go, bind: bindFastNavLinks };
})(typeof window !== 'undefined' ? window : this);
