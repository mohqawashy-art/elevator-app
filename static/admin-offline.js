/* LiftCore Admin — offline banner + IndexedDB write queue + sync (+ fetch/JSON) */
(function (global) {
  'use strict';

  var DB_NAME = 'liftcore-admin';
  var DB_VER = 1;
  var SKIP_PATH_RE = /^\/(login|logout|signup|field|platform|onboard|sw\.js|manifest)/i;
  var SKIP_API_RE = /^\/api\/(live|health|version)(\/|$)/i;

  function openDb() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, DB_VER);
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains('queue')) {
          db.createObjectStore('queue', { keyPath: 'id', autoIncrement: true });
        }
        if (!db.objectStoreNames.contains('kv')) {
          db.createObjectStore('kv');
        }
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function withStore(store, mode, fn) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(store, mode);
        var os = tx.objectStore(store);
        var req = fn(os);
        if (!req) {
          tx.oncomplete = function () { resolve(); };
          tx.onerror = function () { reject(tx.error); };
          return;
        }
        req.onsuccess = function () { resolve(req.result); };
        req.onerror = function () { reject(req.error); };
      });
    });
  }

  function queueAll() {
    return withStore('queue', 'readonly', function (os) { return os.getAll(); })
      .then(function (rows) { return rows || []; });
  }

  function queueAdd(item) {
    return withStore('queue', 'readwrite', function (os) { return os.add(item); });
  }

  function queueDelete(id) {
    return withStore('queue', 'readwrite', function (os) { return os.delete(id); });
  }

  function isNetworkError(err) {
    return !navigator.onLine ||
      (err && (err.name === 'TypeError' || /Failed to fetch|NetworkError/i.test(err.message || '')));
  }

  function shouldSkipUrl(url) {
    try {
      var u = new URL(url, location.origin);
      if (u.origin !== location.origin) return true;
      if (SKIP_PATH_RE.test(u.pathname)) return true;
      if (SKIP_API_RE.test(u.pathname)) return true;
      return false;
    } catch (_e) {
      return true;
    }
  }

  function resolveUrl(input) {
    if (typeof input === 'string') return input;
    if (input && typeof input.url === 'string') return input.url;
    try { return String(input); } catch (_e) { return ''; }
  }

  function headerGet(init, name) {
    if (!init || !init.headers) return '';
    if (typeof Headers !== 'undefined' && init.headers instanceof Headers) {
      return init.headers.get(name) || '';
    }
    if (Array.isArray(init.headers)) {
      for (var i = 0; i < init.headers.length; i++) {
        if (String(init.headers[i][0]).toLowerCase() === name.toLowerCase()) {
          return String(init.headers[i][1] || '');
        }
      }
      return '';
    }
    var key = Object.keys(init.headers || {}).find(function (k) {
      return k.toLowerCase() === name.toLowerCase();
    });
    return key ? String(init.headers[key] || '') : '';
  }

  function queuedJsonResponse(payload) {
    return new Response(JSON.stringify(payload), {
      status: 200,
      statusText: 'OK',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    });
  }

  function parseUrlEncoded(str) {
    var fields = {};
    var params = new URLSearchParams(str || '');
    params.forEach(function (val, key) {
      if (Object.prototype.hasOwnProperty.call(fields, key)) {
        if (!Array.isArray(fields[key])) fields[key] = [fields[key]];
        fields[key].push(val);
      } else {
        fields[key] = val;
      }
    });
    return fields;
  }

  function bodyLooksBinary(body) {
    if (body == null) return false;
    if (typeof Blob !== 'undefined' && body instanceof Blob) return true;
    if (typeof ArrayBuffer !== 'undefined' && body instanceof ArrayBuffer) return true;
    if (typeof ArrayBuffer !== 'undefined' && typeof ArrayBuffer.isView === 'function' && ArrayBuffer.isView(body)) {
      return true;
    }
    return false;
  }

  function csrfToken() {
    if (global.LiftCoreCsrf && global.LiftCoreCsrf.token) {
      return global.LiftCoreCsrf.token() || '';
    }
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? (meta.getAttribute('content') || '') : '';
  }

  function toast(msg, kind) {
    if (global.LiftCoreToast) {
      try { global.LiftCoreToast(msg, kind || 'info'); return; } catch (_e) {}
    }
    try { console.info('[LiftCore offline]', msg); } catch (_e2) {}
  }

  function formHasFiles(form) {
    var inputs = form.querySelectorAll('input[type="file"]');
    for (var i = 0; i < inputs.length; i++) {
      if (inputs[i].files && inputs[i].files.length) return true;
    }
    return false;
  }

  function serializeForm(form) {
    var fields = {};
    var fd = new FormData(form);
    var hasBlob = false;
    fd.forEach(function (val, key) {
      if (typeof Blob !== 'undefined' && val instanceof Blob && !(typeof File !== 'undefined' && val instanceof File && val.name === '')) {
        if (val instanceof File && val.size > 0) hasBlob = true;
        else if (!(val instanceof File) && val.size > 0) hasBlob = true;
      }
      if (typeof val === 'string') {
        if (Object.prototype.hasOwnProperty.call(fields, key)) {
          if (!Array.isArray(fields[key])) fields[key] = [fields[key]];
          fields[key].push(val);
        } else {
          fields[key] = val;
        }
      }
    });
    return { fields: fields, hasBlob: hasBlob };
  }

  function notify(msg) {
    toast(msg, 'warn');
  }

  var api = {
    getPendingCount: function () {
      return queueAll().then(function (items) { return items.length; });
    },

    enqueueForm: function (url, fields, meta) {
      return queueAdd({
        kind: 'form',
        url: url,
        fields: fields,
        label: (meta && meta.label) || url,
        createdAt: Date.now(),
      }).then(function () {
        api.refreshBanner();
        return { ok: true, queued: true };
      });
    },

    enqueueJson: function (url, body, meta) {
      return queueAdd({
        kind: 'json',
        url: url,
        body: body,
        method: (meta && meta.method) || 'POST',
        label: (meta && meta.label) || url,
        createdAt: Date.now(),
      }).then(function () {
        api.refreshBanner();
        return { ok: true, queued: true };
      });
    },

    flushQueue: function () {
      if (!navigator.onLine) return Promise.resolve(0);
      if (global.__LC_ADMIN_OFFLINE_FLUSHING) return Promise.resolve(0);
      global.__LC_ADMIN_OFFLINE_FLUSHING = true;
      return queueAll().then(function (items) {
        items.sort(function (a, b) { return a.createdAt - b.createdAt; });
        var synced = 0;
        function next(i) {
          if (i >= items.length) return Promise.resolve(synced);
          var item = items[i];
          var token = csrfToken();
          var p;
          if (item.kind === 'form') {
            var fields = Object.assign({}, item.fields || {});
            if (token) fields.csrf_token = token;
            var body = new URLSearchParams();
            Object.keys(fields).forEach(function (k) {
              var v = fields[k];
              if (Array.isArray(v)) v.forEach(function (x) { body.append(k, x); });
              else body.append(k, v == null ? '' : String(v));
            });
            p = fetch(item.url, {
              method: item.method || 'POST',
              headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRF-Token': token,
              },
              body: body.toString(),
              credentials: 'same-origin',
            }).then(function (r) {
              if (r.status === 401 || r.status === 403) throw new Error('auth');
              if (!r.ok && r.status >= 500) throw new Error('server');
            });
          } else if (item.kind === 'raw') {
            p = fetch(item.url, {
              method: item.method || 'POST',
              headers: Object.assign({
                'Content-Type': item.contentType || 'text/plain',
                'X-CSRF-Token': token,
              }, item.headers || {}),
              body: item.bodyText || '',
              credentials: 'same-origin',
            }).then(function (r) {
              if (r.status === 401 || r.status === 403) throw new Error('auth');
              if (!r.ok && r.status >= 500) throw new Error('server');
            });
          } else {
            p = fetch(item.url, {
              method: item.method || 'POST',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': token,
              },
              body: JSON.stringify(item.body || {}),
              credentials: 'same-origin',
            }).then(function (r) {
              if (r.status === 401 || r.status === 403) throw new Error('auth');
              if (!r.ok && r.status >= 500) throw new Error('server');
            });
          }
          return p.then(function () {
            return queueDelete(item.id).then(function () {
              synced += 1;
              return next(i + 1);
            });
          }).catch(function () {
            return synced;
          });
        }
        return next(0).then(function (n) {
          if (n > 0) {
            toast('تم مزامنة ' + n + ' عملية معلّقة', 'ok');
            if (global.dispatchEvent) {
              global.dispatchEvent(new CustomEvent('liftcore-admin-synced', { detail: { count: n } }));
            }
          }
          api.refreshBanner();
          return n;
        });
      }).finally(function () {
        global.__LC_ADMIN_OFFLINE_FLUSHING = false;
      });
    },

    ensureBanner: function () {
      var el = document.getElementById('lc-admin-offline-banner');
      if (el) return el;
      el = document.createElement('div');
      el.id = 'lc-admin-offline-banner';
      el.className = 'lc-admin-offline-banner';
      el.hidden = true;
      el.setAttribute('role', 'status');
      el.innerHTML =
        '<span class="lc-admin-offline-banner__text"></span>' +
        '<button type="button" class="lc-admin-offline-banner__sync" hidden>مزامنة الآن</button>';
      var main = document.querySelector('.main') || document.body;
      var header = document.querySelector('header.lc-header, header.header, .lc-header');
      if (header && header.parentNode) {
        if (header.nextSibling) header.parentNode.insertBefore(el, header.nextSibling);
        else header.parentNode.appendChild(el);
      } else if (main.firstChild) {
        main.insertBefore(el, main.firstChild);
      } else {
        main.appendChild(el);
      }
      var btn = el.querySelector('.lc-admin-offline-banner__sync');
      if (btn) {
        btn.addEventListener('click', function () {
          api.flushQueue();
        });
      }
      return el;
    },

    refreshBanner: function () {
      var el = api.ensureBanner();
      var textEl = el.querySelector('.lc-admin-offline-banner__text');
      var syncBtn = el.querySelector('.lc-admin-offline-banner__sync');
      return api.getPendingCount().then(function (n) {
        var offline = !navigator.onLine;
        if (!offline && n === 0) {
          el.hidden = true;
          document.documentElement.classList.remove('lc-admin-offline');
          return;
        }
        el.hidden = false;
        document.documentElement.classList.toggle('lc-admin-offline', offline);
        el.classList.toggle('is-offline', offline);
        el.classList.toggle('has-pending', n > 0);
        var msg;
        if (offline && n > 0) {
          msg = 'وضع بدون إنترنت — ' + n + ' عملية بانتظار الرفع عند عودة الاتصال.';
        } else if (offline) {
          msg = 'وضع بدون إنترنت — تُعرض الصفحات المحفوظة. التعديلات تُحفظ محلياً ثم تُزامن.';
        } else {
          msg = n + ' عملية معلّقة بانتظار المزامنة.';
        }
        if (textEl) textEl.textContent = msg;
        if (syncBtn) syncBtn.hidden = !(n > 0 && navigator.onLine);
      }).catch(function () {});
    },

    bindForms: function () {
      if (document.documentElement.dataset.lcAdminOfflineForms === '1') return;
      document.documentElement.dataset.lcAdminOfflineForms = '1';
      document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!form || form.tagName !== 'FORM') return;
        if (form.getAttribute('data-lc-offline') === '0') return;
        if (navigator.onLine) return;
        var method = ((form.getAttribute('method') || 'GET') + '').toUpperCase();
        if (method === 'GET') return;
        var action = form.getAttribute('action') || location.href;
        if (shouldSkipUrl(action)) return;
        if (formHasFiles(form)) {
          e.preventDefault();
          notify('لا يمكن رفع الملفات بدون إنترنت — أعد المحاولة عند الاتصال');
          return;
        }
        var ser = serializeForm(form);
        if (ser.hasBlob) {
          e.preventDefault();
          notify('هذا النموذج يحتوي مرفقات — يحتاج إنترنت');
          return;
        }
        e.preventDefault();
        api.enqueueForm(action, ser.fields, { label: action }).then(function () {
          notify('حُفظ محلياً — سيُرفع تلقائياً عند عودة الإنترنت');
        });
      }, true);
    },

    /** يحوّل طلب fetch معلّق إلى عنصر طابور — يعيد Promise<boolean> */
    queueFetchRequest: function (url, method, init) {
      init = init || {};
      if (shouldSkipUrl(url)) return Promise.resolve(false);
      if (bodyLooksBinary(init.body)) return Promise.resolve(false);

      var ct = (headerGet(init, 'Content-Type') || '').toLowerCase();
      var body = init.body;

      if (typeof FormData !== 'undefined' && body instanceof FormData) {
        var fields = {};
        var hasFile = false;
        body.forEach(function (val, key) {
          if (typeof File !== 'undefined' && val instanceof File && val.size > 0) {
            hasFile = true;
            return;
          }
          if (typeof val === 'string') {
            if (Object.prototype.hasOwnProperty.call(fields, key)) {
              if (!Array.isArray(fields[key])) fields[key] = [fields[key]];
              fields[key].push(val);
            } else {
              fields[key] = val;
            }
          }
        });
        if (hasFile) return Promise.resolve(false);
        return api.enqueueForm(url, fields, { label: method + ' ' + url }).then(function () {
          return true;
        });
      }

      if (body == null || body === '') {
        return api.enqueueJson(url, {}, { method: method, label: method + ' ' + url }).then(function () {
          return true;
        });
      }

      if (typeof body === 'string') {
        if (ct.indexOf('application/json') >= 0 || /^\s*[\{\[]/.test(body)) {
          var parsed = {};
          try { parsed = JSON.parse(body); } catch (_e) {
            return queueAdd({
              kind: 'raw',
              url: url,
              method: method,
              bodyText: body,
              contentType: ct || 'application/json',
              label: method + ' ' + url,
              createdAt: Date.now(),
            }).then(function () {
              api.refreshBanner();
              return true;
            });
          }
          return api.enqueueJson(url, parsed, { method: method, label: method + ' ' + url }).then(function () {
            return true;
          });
        }
        if (ct.indexOf('application/x-www-form-urlencoded') >= 0 || body.indexOf('=') >= 0) {
          return api.enqueueForm(url, parseUrlEncoded(body), { label: method + ' ' + url }).then(function () {
            return true;
          });
        }
        return queueAdd({
          kind: 'raw',
          url: url,
          method: method,
          bodyText: body,
          contentType: ct || 'text/plain',
          label: method + ' ' + url,
          createdAt: Date.now(),
        }).then(function () {
          api.refreshBanner();
          return true;
        });
      }

      /* كائن عادي نادر كـ body */
      if (typeof body === 'object') {
        try {
          return api.enqueueJson(url, body, { method: method, label: method + ' ' + url }).then(function () {
            return true;
          });
        } catch (_e2) {
          return Promise.resolve(false);
        }
      }
      return Promise.resolve(false);
    },

    patchFetch: function () {
      if (!global.fetch || global.__LC_ADMIN_OFFLINE_FETCH) return;
      global.__LC_ADMIN_OFFLINE_FETCH = true;
      var orig = global.fetch.bind(global);

      global.fetch = function (input, init) {
        init = init || {};
        if (init.__lcOfflineFlush || global.__LC_ADMIN_OFFLINE_FLUSHING) {
          return orig(input, init);
        }

        var method = (
          (init.method) ||
          (input && input.method) ||
          'GET'
        ).toUpperCase();
        if (method === 'GET' || method === 'HEAD' || method === 'OPTIONS') {
          return orig(input, init);
        }

        var url = resolveUrl(input);
        if (!url || shouldSkipUrl(url)) {
          return orig(input, init);
        }

        function asQueuedResponse() {
          return api.queueFetchRequest(url, method, init).then(function (queued) {
            if (!queued) {
              return Promise.reject(new TypeError('Failed to fetch'));
            }
            notify('حُفظ محلياً — سيُرفع تلقائياً عند عودة الإنترنت');
            return queuedJsonResponse({ ok: true, queued: true, offline: true });
          });
        }

        if (!navigator.onLine) {
          return asQueuedResponse();
        }

        return orig(input, init).catch(function (err) {
          if (!isNetworkError(err)) throw err;
          return asQueuedResponse().catch(function () { throw err; });
        });
      };
    },
  };

  global.LiftCoreAdminOffline = api;

  function boot() {
    api.patchFetch();
    api.bindForms();
    api.refreshBanner();
    if (navigator.onLine) api.flushQueue();
  }

  global.addEventListener('online', function () {
    api.refreshBanner();
    api.flushQueue();
  });
  global.addEventListener('offline', function () {
    api.refreshBanner();
  });
  global.addEventListener('liftcore-admin-synced', function () {
    api.refreshBanner();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})(window);
