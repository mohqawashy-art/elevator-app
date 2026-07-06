/* LiftCore Field PWA — Service Worker (scope: /field/) */
'use strict';

const CACHE_NAME = 'liftcore-field-v1';
const PRECACHE = [
  '/static/field-portal.css',
  '/static/field-portal.js',
  '/static/field-offline.js',
  '/static/maintenance-checklist.js',
  '/static/digital-signature.js',
  '/static/document-signatures.js',
  '/static/liftcore-nav.js',
  '/static/images/icon-192.png',
];

function sameOrigin(url) {
  try {
    return new URL(url).origin === self.location.origin;
  } catch (_e) {
    return false;
  }
}

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return Promise.all(
        PRECACHE.map(function (path) {
          return cache.add(path).catch(function () { /* optional asset */ });
        })
      );
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE_NAME; }).map(function (k) {
          return caches.delete(k);
        })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  if (event.request.method !== 'GET' || !sameOrigin(event.request.url)) return;

  var url = new URL(event.request.url);

  if (url.pathname.indexOf('/static/') === 0) {
    event.respondWith(
      caches.match(event.request).then(function (cached) {
        if (cached) return cached;
        return fetch(event.request).then(function (resp) {
          if (resp && resp.ok) {
            var clone = resp.clone();
            caches.open(CACHE_NAME).then(function (c) { c.put(event.request, clone); });
          }
          return resp;
        });
      })
    );
    return;
  }

  if (url.pathname === '/api/field/me') {
    event.respondWith(
      fetch(event.request).then(function (resp) {
        if (resp && resp.ok) {
          var clone = resp.clone();
          caches.open(CACHE_NAME).then(function (c) { c.put(event.request, clone); });
        }
        return resp;
      }).catch(function () {
        return caches.match(event.request);
      })
    );
    return;
  }

  if (url.pathname.indexOf('/field/') === 0) {
    event.respondWith(
      fetch(event.request).then(function (resp) {
        if (resp && resp.ok) {
          var clone = resp.clone();
          caches.open(CACHE_NAME).then(function (c) { c.put(event.request, clone); });
        }
        return resp;
      }).catch(function () {
        return caches.match(event.request);
      })
    );
  }
});
