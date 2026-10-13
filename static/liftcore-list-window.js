/* تنقّل قوائم السيرفر: البحث والفلاتر يغيّران عنوان الصفحة بدل تحميل كل السجلات. */
(function (global) {
  'use strict';

  function go(updates) {
    var url = new URL(global.location.href);
    Object.keys(updates || {}).forEach(function (key) {
      var value = updates[key];
      if (value === undefined || value === null || value === '') url.searchParams.delete(key);
      else url.searchParams.set(key, value);
    });
    if (!Object.prototype.hasOwnProperty.call(updates || {}, 'page')) url.searchParams.set('page', '1');
    var next = url.pathname + (url.searchParams.toString() ? '?' + url.searchParams.toString() : '');
    if (next !== global.location.pathname + global.location.search) global.location.href = next;
  }

  function serverList() {
    return global.LIST_META && global.LIST_META.server;
  }

  global.lcListGo = function (updates) {
    if (!serverList()) return false;
    go(updates || {});
    return true;
  };

  global.lcListSearch = function (el) {
    if (!serverList()) {
      if (typeof global.filterTable === 'function') global.filterTable();
      return;
    }
    clearTimeout(global._lcListSearchTimer);
    global._lcListSearchTimer = setTimeout(function () {
      go({ q: ((el && el.value) || '').trim(), page: '1' });
    }, 400);
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
})(typeof window !== 'undefined' ? window : this);
