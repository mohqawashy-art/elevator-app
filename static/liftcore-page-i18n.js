/**
 * LiftCore — مساعدات i18n مشتركة لصفحات CRUD (نمط العملاء/العقود)
 */
(function (global) {
  'use strict';

  function isEn() {
    return (global.__LC_LANG || 'ar') === 'en';
  }

  function tr(key) {
    if (!key || !isEn()) return key;
    if (global.LiftCoreI18n && global.LiftCoreI18n.t) {
      var v = global.LiftCoreI18n.t(key);
      if (v && v !== key) return v;
    }
    var d = global.__LC_TRANSLATIONS || {};
    return d[key] || key;
  }

  function updateTemplateLinks() {
    var lang = isEn() ? 'en' : 'ar';
    document.querySelectorAll('[data-lc-template-base]').forEach(function (a) {
      var base = a.getAttribute('data-lc-template-base');
      if (base) a.href = base + (base.indexOf('?') >= 0 ? '&' : '?') + 'lang=' + lang;
    });
  }

  function applyMarked(root) {
    if (global.LiftCoreI18n && global.LiftCoreI18n.applyLcMarked) {
      global.LiftCoreI18n.applyLcMarked(root || document, global.__LC_LANG || 'ar');
    }
  }

  function bootPageI18n(opts) {
    opts = opts || {};
    updateTemplateLinks();
    applyMarked(document);
    if (typeof opts.onApply === 'function') opts.onApply(isEn());
    global.__lcRefreshPage = function () {
      if (typeof opts.onRefresh === 'function') opts.onRefresh(isEn());
      updateTemplateLinks();
      applyMarked(document);
      if (typeof opts.onApply === 'function') opts.onApply(isEn());
    };
    document.addEventListener('liftcore:lang', function () {
      updateTemplateLinks();
      applyMarked(document);
      if (typeof opts.onApply === 'function') opts.onApply(isEn());
    });
  }

  global.LiftCorePageI18n = {
    isEn: isEn,
    tr: tr,
    applyMarked: applyMarked,
    updateTemplateLinks: updateTemplateLinks,
    bootPageI18n: bootPageI18n,
  };
})(typeof window !== 'undefined' ? window : this);
