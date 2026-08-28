/**
 * LiftCore — تشغيل الترجمة بعد تحميل كل الصفحة (يُحمّل defer بعد سكربتات الصفحة)
 */
(function () {
  'use strict';
  function boot() {
    var lang = window.__LC_LANG;
    if (!lang) {
      try { lang = localStorage.getItem('liftcore_lang'); } catch (e) { lang = null; }
    }
    if (lang !== 'ar' && lang !== 'en') lang = 'ar';
    window.__LC_LANG = lang;
    if (window.LiftCoreI18n && window.LiftCoreI18n.setLang) {
      if (typeof window.setLang !== 'function') {
        try { window.setLang = window.LiftCoreI18n.setLang; } catch (e) { /* ignore */ }
      }
      window.LiftCoreI18n.apply(lang);
    }
    if (window.LiftCorePageI18n && window.LiftCorePageI18n.updateTemplateLinks) {
      window.LiftCorePageI18n.updateTemplateLinks();
    }
  }
  boot();
  window.addEventListener('load', boot);
})();
