/**
 * LiftCore — CSRF token for fetch POST/PUT/PATCH/DELETE + form injection.
 */
(function (global) {
  'use strict';

  function token() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') || '' : '';
  }

  function injectFormTokens() {
    var t = token();
    if (!t) return;
    document.querySelectorAll('form').forEach(function (form) {
      var method = ((form.getAttribute('method') || 'GET') + '').toUpperCase();
      if (method === 'GET') return;
      if (form.querySelector('input[name="csrf_token"]')) return;
      var inp = document.createElement('input');
      inp.type = 'hidden';
      inp.name = 'csrf_token';
      inp.value = t;
      form.appendChild(inp);
    });
  }

  function patchFetch() {
    if (!global.fetch || global.__LC_CSRF_PATCHED) return;
    global.__LC_CSRF_PATCHED = true;
    var orig = global.fetch.bind(global);
    global.fetch = function (input, init) {
      init = init || {};
      var method = ((init.method || 'GET') + '').toUpperCase();
      if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
        var headers = new Headers(init.headers || {});
        var t = token();
        if (t && !headers.has('X-CSRF-Token')) {
          headers.set('X-CSRF-Token', t);
        }
        init.headers = headers;
      }
      return orig(input, init);
    };
  }

  patchFetch();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectFormTokens);
  } else {
    injectFormTokens();
  }
  global.LiftCoreCsrf = { token: token, injectFormTokens: injectFormTokens };
})(window);
