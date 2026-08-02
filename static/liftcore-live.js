(function (global) {
  'use strict';

  var POLL_MS = 4000;
  var lastRevision = null;
  var pendingRevision = null;
  var syncing = false;
  var toastTimer = null;

  var CLIENT_SELECT_WRAPS = [
    ['elev-client-select', 'f-client-sel'],
    ['contract-client-select', 'f-client-sel'],
    ['client-select', 'f-client-sel'],
  ];

  function pageKey() {
    var path = (global.location.pathname || '/').replace(/\/+$/, '') || '/';
    if (path.indexOf('/login') >= 0) return null;
    if (path.indexOf('/print') >= 0 || path.indexOf('/report') >= 0) return null;
    if (path.indexOf('/field') === 0) return null;
    if (path.indexOf('visit-report') >= 0 || path.indexOf('fault-report') >= 0) return null;
    if (path === '/') return 'dashboard';
    return path.replace(/^\//, '').split('/')[0];
  }

  function sessionLockedUi() {
    var root = global.document.documentElement;
    if (root && root.classList.contains('lc-session-locked')) return true;
    return !!global.document.getElementById('lc-idle-screensaver.open');
  }

  function onSessionLocked() {
    try { global.sessionStorage.setItem('lc_idle_locked', '1'); } catch (e) { /* ignore */ }
    global.__LC_SESSION_LOCKED = true;
    if (global.document.documentElement) {
      global.document.documentElement.classList.add('lc-session-locked');
    }
    if (global.LiftCoreIdleScreensaver && typeof global.LiftCoreIdleScreensaver.show === 'function') {
      global.LiftCoreIdleScreensaver.show();
    }
  }

  function canSyncNow() {
    if (sessionLockedUi()) return false;
    if (global.document.querySelector('.modal-overlay.open')) return false;
    var ae = global.document.activeElement;
    if (ae && ae.closest && ae.closest('.modal-overlay.open')) return false;
    return true;
  }

  function showToast(msg) {
    var el = global.document.getElementById('lc-live-toast');
    if (!el) {
      el = global.document.createElement('div');
      el.id = 'lc-live-toast';
      el.setAttribute('role', 'status');
      el.style.cssText =
        'position:fixed;bottom:18px;left:18px;z-index:12000;padding:10px 14px;' +
        'background:rgba(19,27,39,.95);color:#e4eaf5;border:1px solid rgba(42,127,255,.35);' +
        'border-radius:8px;font-size:12px;font-family:inherit;opacity:0;transition:opacity .2s ease;pointer-events:none';
      global.document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.opacity = '1';
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.style.opacity = '0'; }, 2200);
  }

  function mergeArray(name, rows) {
    if (!Array.isArray(rows)) return false;
    var arr = global[name];
    if (!arr || !Array.isArray(arr)) return false;
    arr.length = 0;
    rows.forEach(function (row) { arr.push(row); });
    return true;
  }

  function mergeObject(name, obj) {
    if (!obj || typeof obj !== 'object') return false;
    var target = global[name];
    if (!target || typeof target !== 'object' || Array.isArray(target)) return false;
    Object.keys(target).forEach(function (k) { delete target[k]; });
    Object.assign(target, obj);
    return true;
  }

  function applyLiveData(data) {
    if (!data) return 0;
    var merged = 0;
    Object.keys(data).forEach(function (key) {
      if (key.charAt(0) === '_') return;
      var val = data[key];
      if (key === 'STATS' && global.STATS && val && typeof val === 'object') {
        Object.assign(global.STATS, val);
        merged += 1;
        return;
      }
      if (key === 'UNASSIGNED_FAULTS' && typeof val === 'number') {
        global.UNASSIGNED_FAULTS = val;
        merged += 1;
        return;
      }
      if (mergeArray(key, val)) merged += 1;
      else if (key === 'ELEVATOR_LOOKUP') {
        if (mergeObject(key, val)) merged += 1;
      }
    });
    return merged;
  }

  var PAGE_FILTER_SOURCE = {
    'clients': 'CUSTOMERS',
    'contracts': 'CONTRACTS',
    'elevators': 'ELEVATORS',
    'technicians': 'TECHNICIANS',
    'maintenance-visits': 'VISITS',
    'faults': 'FAULTS',
    'parts-billing': 'PARTS',
    'inventory': 'ITEMS',
    'stock-movements': 'MOVEMENTS',
    'revenues': 'REVENUES',
    'expenses': 'EXPENSES',
    'invoices': 'INVOICES',
  };

  function resyncFilteredFromMaster() {
    if (!global.filtered || !Array.isArray(global.filtered)) return null;
    var masterName = global.__lcFilteredSource || PAGE_FILTER_SOURCE[pageKey()];
    if (!masterName || !Array.isArray(global[masterName])) return null;
    global.filtered.length = 0;
    global[masterName].forEach(function (row) { global.filtered.push(row); });
    return masterName;
  }

  function refreshClientSelects() {
    if (typeof global.LcClientSelect === 'undefined' || !Array.isArray(global.CUSTOMERS)) return;
    CLIENT_SELECT_WRAPS.forEach(function (pair) {
      if (!global.LcClientSelect.isUpgraded(pair[0])) return;
      var hid = global.document.getElementById(pair[1]);
      global.LcClientSelect.setCustomers(pair[0], global.CUSTOMERS, hid ? hid.value : '');
    });
  }

  function refreshUiAfterLive() {
    // تحديث تلقائي وليس تفاعل مستخدم — نُبقي المستخدم على صفحته الحالية
    global.__lcPreservePage = true;
    try {
      if (typeof global.filterTable === 'function') {
        global.filterTable();
      } else if (typeof global.applyFilters === 'function') {
        global.applyFilters();
      } else {
        resyncFilteredFromMaster();
        if (typeof global.__lcRefreshPage === 'function') global.__lcRefreshPage();
      }
    } finally {
      global.__lcPreservePage = false;
    }
    if (typeof global.updateStats === 'function') global.updateStats();
    if (typeof global.updateDashboard === 'function') global.updateDashboard();
    if (typeof global.loadCharts === 'function') global.loadCharts();
    if (typeof global.fillCitySelects === 'function') global.fillCitySelects();
    if (typeof global.applyWorkMonth === 'function') global.applyWorkMonth();
    if (typeof global.refreshElevatorMap === 'function') global.refreshElevatorMap(false);
    refreshClientSelects();
    if (global.LiftCoreDisplay && global.LiftCoreDisplay.applyDom) {
      global.LiftCoreDisplay.applyDom(global.document, global.LiftCoreDisplay.currentLang());
    }
    global.document.dispatchEvent(new CustomEvent('liftcore:live-sync'));
  }

  function fetchAndApply(revision) {
    var key = pageKey();
    if (!key || syncing) return;
    syncing = true;
    global.fetch('/api/live/sync?page=' + encodeURIComponent(key), { credentials: 'same-origin' })
      .then(function (r) {
        if (r.status === 401) return null;
        if (r.status === 423) {
          onSessionLocked();
          return null;
        }
        return r.json();
      })
      .then(function (payload) {
        if (!payload) return;
        lastRevision = payload.revision != null ? payload.revision : revision;
        if (payload.unsupported) {
          if (canSyncNow()) global.location.reload();
          return;
        }
        var merged = applyLiveData(payload.data);
        if (!merged) {
          if (canSyncNow()) global.location.reload();
          return;
        }
        refreshUiAfterLive();
        showToast(global.__LC_LANG === 'en' ? 'Data updated' : 'تم تحديث البيانات');
      })
      .catch(function () { /* ignore */ })
      .finally(function () { syncing = false; });
  }

  function tryPendingSync() {
    if (pendingRevision != null && canSyncNow()) {
      var rev = pendingRevision;
      pendingRevision = null;
      fetchAndApply(rev);
    }
  }

  function onRevisionChange(revision) {
    if (!canSyncNow()) {
      pendingRevision = revision;
      showToast(global.__LC_LANG === 'en' ? 'Updates waiting — close the form' : 'تحديثات بانتظار — أغلق النموذج');
      return;
    }
    fetchAndApply(revision);
  }

  function pollRevision() {
    if (!pageKey()) return;
    global.fetch('/api/live/revision', { credentials: 'same-origin' })
      .then(function (r) {
        if (r.status === 401) return null;
        if (r.status === 423) {
          onSessionLocked();
          return null;
        }
        return r.json();
      })
      .then(function (payload) {
        if (!payload || payload.revision == null) return;
        if (lastRevision == null) {
          lastRevision = payload.revision;
          return;
        }
        if (payload.revision !== lastRevision) onRevisionChange(payload.revision);
      })
      .catch(function () { /* ignore */ });
  }

  function boot() {
    if (!pageKey()) return;
    pollRevision();
    setInterval(pollRevision, POLL_MS);
    global.document.addEventListener('click', function (e) {
      if (e.target.closest('.modal-close, [onclick*="closeModal"]')) {
        setTimeout(tryPendingSync, 350);
      }
    });
  }

  if (global.document.readyState === 'loading') {
    global.document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  global.LiftCoreLive = {
    poll: pollRevision,
    pageKey: pageKey,
    applyLiveData: applyLiveData,
    refreshUiAfterLive: refreshUiAfterLive,
  };
})(typeof window !== 'undefined' ? window : this);
