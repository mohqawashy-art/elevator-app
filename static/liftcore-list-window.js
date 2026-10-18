/* تنقّل قوائم السيرفر: البحث ينتظر اكتمال الكلمة ثم يغيّر العنوان. */
(function (global) {
  'use strict';

  var SERVER_WAIT_MS = 1200;
  var CLIENT_WAIT_MS = 500;
  var RESUME_KEY = 'lcSearchResume';

  function go(updates) {
    var url = new URL(global.location.href);
    Object.keys(updates || {}).forEach(function (key) {
      var value = updates[key];
      if (value === undefined || value === null || value === '') url.searchParams.delete(key);
      else url.searchParams.set(key, value);
    });
    if (!Object.prototype.hasOwnProperty.call(updates || {}, 'page')) url.searchParams.set('page', '1');
    global.location.href = url.pathname + (url.searchParams.toString() ? '?' + url.searchParams.toString() : '');
  }

  function serverList() {
    return global.LIST_META && global.LIST_META.server;
  }

  function currentQuery() {
    try {
      return new URL(global.location.href).searchParams.get('q') || '';
    } catch (e) {
      return '';
    }
  }

  function markResume(el) {
    if (!el || !el.id) return;
    try {
      global.sessionStorage.setItem(RESUME_KEY, JSON.stringify({
        id: el.id,
        ts: Date.now()
      }));
    } catch (e) { /* ignore */ }
  }

  function resumeSearch() {
    var raw;
    try { raw = global.sessionStorage.getItem(RESUME_KEY); } catch (e) { return; }
    if (!raw) return;
    try { global.sessionStorage.removeItem(RESUME_KEY); } catch (e2) { /* ignore */ }
    var info;
    try { info = JSON.parse(raw); } catch (e3) { return; }
    if (!info || !info.id || !info.ts || (Date.now() - info.ts) > 20000) return;
    var el = global.document.getElementById(info.id);
    if (!el || el.disabled || el.readOnly) return;
    try { el.focus({ preventScroll: true }); } catch (e4) {
      try { el.focus(); } catch (e5) { return; }
    }
    var len = String(el.value || '').length;
    try { el.setSelectionRange(len, len); } catch (e6) { /* ignore */ }
  }

  function invokeNamed(attr) {
    if (attr.indexOf('InstallContracts') >= 0) {
      if (global.InstallContracts && typeof global.InstallContracts.filter === 'function') global.InstallContracts.filter();
      return;
    }
    if (attr.indexOf('applyCustodyFilters') >= 0) {
      if (typeof global.applyCustodyFilters === 'function') global.applyCustodyFilters();
      return;
    }
    if (attr.indexOf('applyFilters') >= 0) {
      if (typeof global.applyFilters === 'function') global.applyFilters();
      return;
    }
    if (attr.indexOf('filterRows') >= 0) {
      if (typeof global.filterRows === 'function') global.filterRows();
      return;
    }
    if (typeof global.filterTable === 'function') global.filterTable();
  }

  function runClientFilter(el) {
    if (el && el.dataset && el.dataset.lcSearchFn) {
      invokeNamed(el.dataset.lcSearchFn);
      return;
    }
    var id = el && el.id;
    if (id === 'cust-f-search' && typeof global.applyCustodyFilters === 'function') {
      global.applyCustodyFilters();
      return;
    }
    if (typeof global.filterTable === 'function') global.filterTable();
    else if (typeof global.applyFilters === 'function') global.applyFilters();
    else if (global.InstallContracts && typeof global.InstallContracts.filter === 'function') global.InstallContracts.filter();
  }

  function commitServerSearch(el) {
    if (!el || el._lcComposing) return;
    var q = String(el.value || '').trim();
    if (q === String(currentQuery() || '').trim()) return;
    markResume(el);
    go({ q: q, page: '1' });
  }

  function schedule(el, wait, fn) {
    clearTimeout(el._lcSearchTimer);
    el._lcSearchTimer = setTimeout(function () {
      if (el._lcComposing) return;
      fn(el);
    }, wait);
  }

  global.lcListSearch = function (el) {
    if (!el || el._lcComposing) {
      if (el) clearTimeout(el._lcSearchTimer);
      return;
    }
    if (!serverList()) {
      schedule(el, CLIENT_WAIT_MS, runClientFilter);
      return;
    }
    schedule(el, SERVER_WAIT_MS, commitServerSearch);
  };

  global.lcListSearchNow = function (el) {
    if (!el) return;
    clearTimeout(el._lcSearchTimer);
    el._lcComposing = false;
    if (el.dataset && el.dataset.lcSearchFn) {
      invokeNamed(el.dataset.lcSearchFn);
      return;
    }
    if (!serverList()) {
      runClientFilter(el);
      return;
    }
    commitServerSearch(el);
  };

  global.lcListGo = function (updates) {
    if (!serverList()) return false;
    go(updates || {});
    return true;
  };

  global.lcListParam = function (key, value) {
    if (!serverList()) {
      if (typeof global.filterTable === 'function') global.filterTable();
      return;
    }
    var updates = { page: '1' };
    updates[key] = value || '';
    go(updates);
  };

  function isLiveSearchInput(el) {
    if (!el || el.tagName !== 'INPUT') return false;
    var type = (el.type || 'text').toLowerCase();
    if (type === 'date' || type === 'number' || type === 'hidden' || type === 'checkbox' || type === 'password' || type === 'file' || type === 'range') return false;
    if (el.classList && (el.classList.contains('map-picker-search') || el.classList.contains('lc-client-select-input') || el.classList.contains('lc-gmp-autocomplete'))) return false;
    var id = el.id || '';
    if (id === 'search-input' || id === 'f-search' || id === 'cust-f-search') return true;
    if (el.classList && el.classList.contains('search-input')) return true;
    if (el.dataset && el.dataset.lcSearchFn) return true;
    return false;
  }

  function bindInlineFilters(root) {
    var nodes = (root || global.document).querySelectorAll('input.search-input, #search-input, #f-search, #cust-f-search');
    Array.prototype.forEach.call(nodes, function (el) {
      if (!el.getAttribute('autocomplete')) el.setAttribute('autocomplete', 'off');
      if (el.dataset.lcSearchWait) return;
      var attr = (el.getAttribute('oninput') || '').replace(/\s+/g, '');
      if (!attr || attr.indexOf('lcListSearch') >= 0) {
        el.dataset.lcSearchWait = '1';
        return;
      }
      if (!/^(?:filterTable\(\)|applyFilters\(\)|applyCustodyFilters\(\)|filterRows\(\)|window\.InstallContracts\.filter\(\))$/.test(attr)) return;
      el.dataset.lcSearchWait = '1';
      el.dataset.lcSearchFn = attr;
      el.removeAttribute('oninput');
      el.addEventListener('input', function () {
        if (el._lcComposing) return;
        schedule(el, CLIENT_WAIT_MS, function () { invokeNamed(attr); });
      });
    });
  }

  function bindKeys() {
    if (global.document.documentElement.dataset.lcSearchKeys) return;
    global.document.documentElement.dataset.lcSearchKeys = '1';
    global.document.addEventListener('compositionstart', function (e) {
      var el = e.target;
      if (!isLiveSearchInput(el)) return;
      el._lcComposing = true;
      clearTimeout(el._lcSearchTimer);
    }, true);
    global.document.addEventListener('compositionend', function (e) {
      var el = e.target;
      if (!el || !isLiveSearchInput(el)) return;
      el._lcComposing = false;
      if (el.dataset && el.dataset.lcSearchFn) {
        schedule(el, CLIENT_WAIT_MS, function () { invokeNamed(el.dataset.lcSearchFn); });
        return;
      }
      global.lcListSearch(el);
    }, true);
    global.document.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' || e.isComposing || e.shiftKey || e.ctrlKey || e.altKey || e.metaKey) return;
      var el = e.target;
      if (!isLiveSearchInput(el)) return;
      if (el.form && el.name === 'q' && !el.classList.contains('search-input') && el.id !== 'search-input' && el.id !== 'f-search') return;
      e.preventDefault();
      global.lcListSearchNow(el);
    }, true);
  }

  function boot() {
    bindKeys();
    bindInlineFilters(global.document);
    resumeSearch();
  }

  if (global.document.readyState === 'complete') boot();
  else global.document.addEventListener('DOMContentLoaded', boot);
})(typeof window !== 'undefined' ? window : this);
