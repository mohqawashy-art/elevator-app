/* LiftCore Admin PWA — static shell + visited pages + offline fallback */
'use strict';

const CACHE = 'liftcore-admin-v18';
const OFFLINE_FALLBACK = '/static/admin-offline-fallback.html';
const PRECACHE = [
  '/static/liftcore-shell.css?v=51',
  '/static/liftcore-admin-mobile.css?v=7',
  '/static/liftcore-mobile-touch.css?v=2',
  '/static/liftcore-theme.css',
  '/static/liftcore-layout.css?v=5',
  '/static/liftcore-sticky-top.css?v=6',
  '/static/liftcore-shell.js?v=24',
  '/static/liftcore-hotkeys.js?v=4',
  '/static/contracts-zero-hotfix.js?v=3',
  '/static/liftcore-mobile-touch.js?v=2',
  '/static/liftcore-csrf.js?v=1',
  '/static/admin-offline.js?v=1',
  '/static/admin-offline-fallback.html',
  '/static/images/icon-192.png',
];

function isStaticAsset(url) {
  return url.pathname.indexOf('/static/') === 0;
}

function isStyleOrScript(url) {
  return /\.(css|js)(\?|$)/i.test(url.pathname + (url.search || ''));
}

/** ملفات المستخدم (شعار الشركة وغيرها) — لا تُخزَّن حتى يظهر التحديث فوراً */
function isUserUpload(url) {
  return url.pathname.indexOf('/static/uploads/') === 0;
}

function isDocumentRequest(request) {
  if (request.mode === 'navigate') return true;
  var accept = (request.headers && request.headers.get('accept')) || '';
  return accept.indexOf('text/html') >= 0;
}

/** صفحات تطبيق المكتب القابلة للعرض بدون نت بعد زيارة سابقة */
function isCacheableAdminPage(url) {
  var p = url.pathname || '';
  if (p.indexOf('/static/') === 0) return false;
  if (p.indexOf('/api/') === 0) return false;
  if (p.indexOf('/field') === 0) return false;
  if (p.indexOf('/platform') === 0) return false;
  if (p.indexOf('/operator') === 0) return false;
  if (p.indexOf('/onboard') === 0) return false;
  if (p.indexOf('/auth/') === 0) return false;
  if (p === '/login' || p === '/logout' || p === '/signup' || p === '/sw.js') return false;
  if (p === '/clients' || p.indexOf('/clients/') === 0) return false;
  if (p === '/' || p === '/pricing' || p === '/coming-soon' || p === '/product') return false;
  return true;
}

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      return Promise.all(
        PRECACHE.map(function (path) {
          return cache.add(path).catch(function () {});
        })
      );
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE; }).map(function (k) {
          return caches.delete(k);
        })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  if (event.request.method !== 'GET') return;
  var url;
  try {
    url = new URL(event.request.url);
  } catch (_e) {
    return;
  }
  if (url.origin !== self.location.origin) return;

  if (isStaticAsset(url)) {
    if (isUserUpload(url)) {
      event.respondWith(
        fetch(event.request, { cache: 'no-store' }).catch(function () {
          return caches.match(event.request);
        })
      );
      return;
    }

    if (isStyleOrScript(url) || url.pathname.indexOf('/static/admin-offline') === 0) {
      event.respondWith(
        fetch(event.request).then(function (resp) {
          if (resp && resp.ok) {
            var clone = resp.clone();
            caches.open(CACHE).then(function (c) { c.put(event.request, clone); });
          }
          return resp;
        }).catch(function () {
          return caches.match(event.request);
        })
      );
      return;
    }

    event.respondWith(
      caches.match(event.request).then(function (cached) {
        if (cached) return cached;
        return fetch(event.request).then(function (resp) {
          if (resp && resp.ok) {
            var clone = resp.clone();
            caches.open(CACHE).then(function (c) { c.put(event.request, clone); });
          }
          return resp;
        });
      })
    );
    return;
  }

  if (!isDocumentRequest(event.request) || !isCacheableAdminPage(url)) {
    return;
  }

  event.respondWith(
    fetch(event.request).catch(function () {
      return caches.match(OFFLINE_FALLBACK);
    })
  );
});
