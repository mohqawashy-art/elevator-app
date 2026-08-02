/* LiftCore Admin PWA */
'use strict';

const CACHE = 'liftcore-admin-v8';
const PRECACHE = [
  '/static/liftcore-shell.css?v=44',
  '/static/liftcore-admin-mobile.css?v=6',
  '/static/liftcore-mobile-touch.css?v=2',
  '/static/liftcore-theme.css',
  '/static/liftcore-layout.css?v=5',
  '/static/liftcore-sticky-top.css?v=6',
  '/static/liftcore-shell.js?v=24',
  '/static/contracts-zero-hotfix.js?v=3',
  '/static/liftcore-mobile-touch.js?v=2',
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
  if (!isStaticAsset(url)) return;

  if (isUserUpload(url)) {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' }).catch(function () {
        return caches.match(event.request);
      })
    );
    return;
  }

  if (isStyleOrScript(url)) {
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
});
