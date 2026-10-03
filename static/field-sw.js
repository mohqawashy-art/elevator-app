/* LiftCore Field PWA — Service Worker (scope: /field/) */
'use strict';

var CACHE_NAME = 'liftcore-field-v7';
var PRECACHE = [
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

function fetchWithTimeout(request, ms) {
  return new Promise(function (resolve, reject) {
    var timer = setTimeout(function () {
      reject(new Error('timeout'));
    }, ms);
    fetch(request).then(function (resp) {
      clearTimeout(timer);
      resolve(resp);
    }, function (err) {
      clearTimeout(timer);
      reject(err);
    });
  });
}

function offlinePage() {
  return new Response(
    '<!DOCTYPE html><html lang="ar" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LiftCore</title><body style="margin:0;background:#070a10;color:#f2f5fa;font-family:sans-serif"><p style="padding:28px;line-height:1.7">تعذّر فتح بوابة الفني. أغلق الصفحة وافتح الرابط من كروم مرة أخرى.</p></body></html>',
    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
  );
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
  if (url.pathname === '/field/sw.js') return;

  if (url.pathname.indexOf('/static/') === 0) {
    event.respondWith(
      fetchWithTimeout(event.request, 8000).then(function (resp) {
        if (resp && resp.ok && !resp.redirected) {
          var copy = resp.clone();
          caches.open(CACHE_NAME).then(function (cache) {
            cache.put(event.request, copy).catch(function () {});
          });
        }
        return resp;
      }).catch(function () {
        return caches.match(event.request).then(function (cached) {
          return cached || new Response('', { status: 504 });
        });
      })
    );
    return;
  }

  if (url.pathname === '/api/field/me' || url.pathname === '/api/live/revision') {
    event.respondWith(fetch(event.request).catch(function () {
      return new Response('{"ok":false}', {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      });
    }));
    return;
  }

  if (url.pathname === '/field' || url.pathname.indexOf('/field/') === 0) {
    event.respondWith(
      fetchWithTimeout(event.request, 12000).catch(function () {
        return caches.match(event.request).then(function (cached) {
          return cached || offlinePage();
        });
      })
    );
  }
});
