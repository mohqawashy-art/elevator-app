/* LiftCore Admin PWA — تخزين مؤقت لملفات الواجهة */
'use strict';

const CACHE = 'liftcore-admin-v1';
const PRECACHE = [
  '/static/liftcore-shell.css',
  '/static/liftcore-admin-mobile.css',
  '/static/liftcore-theme.css',
  '/static/liftcore-layout.css',
  '/static/liftcore-shell.js',
  '/static/images/icon-192.png',
];

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
  if (url.pathname.indexOf('/static/') !== 0) return;
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
