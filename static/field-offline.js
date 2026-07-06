/* LiftCore Field — IndexedDB drafts + sync queue */
(function (global) {
  'use strict';

  var DB_NAME = 'liftcore-field';
  var DB_VER = 1;

  function openDb() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, DB_VER);
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains('kv')) db.createObjectStore('kv');
        if (!db.objectStoreNames.contains('queue')) {
          db.createObjectStore('queue', { keyPath: 'id', autoIncrement: true });
        }
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function txStore(store, mode) {
    return openDb().then(function (db) {
      return db.transaction(store, mode).objectStore(store);
    });
  }

  function kvGet(key) {
    return txStore('kv', 'readonly').then(function (store) {
      return new Promise(function (resolve, reject) {
        var req = store.get(key);
        req.onsuccess = function () { resolve(req.result); };
        req.onerror = function () { reject(req.error); };
      });
    });
  }

  function kvPut(key, value) {
    return txStore('kv', 'readwrite').then(function (store) {
      return new Promise(function (resolve, reject) {
        var req = store.put(value, key);
        req.onsuccess = function () { resolve(); };
        req.onerror = function () { reject(req.error); };
      });
    });
  }

  function kvDelete(key) {
    return txStore('kv', 'readwrite').then(function (store) {
      return new Promise(function (resolve, reject) {
        var req = store.delete(key);
        req.onsuccess = function () { resolve(); };
        req.onerror = function () { reject(req.error); };
      });
    });
  }

  function queueAll() {
    return txStore('queue', 'readonly').then(function (store) {
      return new Promise(function (resolve, reject) {
        var req = store.getAll();
        req.onsuccess = function () { resolve(req.result || []); };
        req.onerror = function () { reject(req.error); };
      });
    });
  }

  function queueAdd(item) {
    return txStore('queue', 'readwrite').then(function (store) {
      return new Promise(function (resolve, reject) {
        var req = store.add(item);
        req.onsuccess = function () { resolve(req.result); };
        req.onerror = function () { reject(req.error); };
      });
    });
  }

  function queueDelete(id) {
    return txStore('queue', 'readwrite').then(function (store) {
      return new Promise(function (resolve, reject) {
        var req = store.delete(id);
        req.onsuccess = function () { resolve(); };
        req.onerror = function () { reject(req.error); };
      });
    });
  }

  function isNetworkError(err) {
    return !navigator.onLine || (err && (err.name === 'TypeError' || err.message === 'Failed to fetch'));
  }

  var api = {
    cacheMePayload: function (payload) {
      return kvPut('me', { savedAt: Date.now(), payload: payload });
    },

    getMePayload: function () {
      return kvGet('me').then(function (row) {
        return row && row.payload ? row.payload : null;
      });
    },

    saveDraft: function (key, data) {
      return kvPut('draft:' + key, { savedAt: Date.now(), data: data });
    },

    loadDraft: function (key) {
      return kvGet('draft:' + key).then(function (row) {
        return row && row.data ? row.data : null;
      });
    },

    deleteDraft: function (key) {
      return kvDelete('draft:' + key);
    },

    getPendingCount: function () {
      return queueAll().then(function (items) { return items.length; });
    },

    enqueueJson: function (url, body, meta) {
      return queueAdd({
        kind: 'json',
        url: url,
        body: body,
        label: (meta && meta.label) || url,
        draftKey: meta && meta.draftKey,
        createdAt: Date.now(),
      });
    },

    enqueueForm: function (url, fields, meta) {
      return queueAdd({
        kind: 'form',
        url: url,
        fields: fields,
        label: (meta && meta.label) || url,
        createdAt: Date.now(),
      });
    },

    postJson: function (url, body, meta) {
      meta = meta || {};
      if (meta.draftKey) {
        api.saveDraft(meta.draftKey, body);
      }
      if (!navigator.onLine) {
        return api.enqueueJson(url, body, meta).then(function () {
          return { ok: true, queued: true };
        });
      }
      return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        credentials: 'same-origin',
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.ok) throw new Error(data.error || 'تعذّر الحفظ');
          if (meta.draftKey) api.deleteDraft(meta.draftKey);
          return data;
        })
        .catch(function (err) {
          if (isNetworkError(err)) {
            return api.enqueueJson(url, body, meta).then(function () {
              return { ok: true, queued: true };
            });
          }
          throw err;
        });
    },

    flushQueue: function () {
      if (!navigator.onLine) return Promise.resolve(0);
      return queueAll().then(function (items) {
        items.sort(function (a, b) { return a.createdAt - b.createdAt; });
        var synced = 0;
        function next(i) {
          if (i >= items.length) return Promise.resolve(synced);
          var item = items[i];
          var p;
          if (item.kind === 'form') {
            p = fetch(item.url, {
              method: 'POST',
              headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
              body: new URLSearchParams(item.fields).toString(),
              credentials: 'same-origin',
            }).then(function (r) {
              if (!r.ok) throw new Error('form sync failed');
            });
          } else {
            p = fetch(item.url, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(item.body),
              credentials: 'same-origin',
            }).then(function (r) { return r.json(); }).then(function (d) {
              if (!d.ok) throw new Error(d.error || 'sync failed');
            });
          }
          return p.then(function () {
            return queueDelete(item.id).then(function () {
              if (item.draftKey) return api.deleteDraft(item.draftKey);
            }).then(function () {
              synced += 1;
              return next(i + 1);
            });
          }).catch(function () { return synced; });
        }
        return next(0);
      });
    },

    notifyQueued: function (queued) {
      if (queued) {
        alert('📴 حُفظ محلياً — سيُرفع تلقائياً عند عودة الإنترنت');
      }
    },
  };

  global.LiftCoreFieldOffline = api;

  global.addEventListener('online', function () {
    api.flushQueue().then(function (n) {
      if (n > 0 && global.dispatchEvent) {
        global.dispatchEvent(new CustomEvent('liftcore-field-synced', { detail: { count: n } }));
      }
    });
    if (global.LiftCoreFieldPortal && global.LiftCoreFieldPortal.refreshStatus) {
      global.LiftCoreFieldPortal.refreshStatus();
    }
  });
})(window);
