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
      try {
        Object.defineProperty(window, 'setLang', {
          value: window.LiftCoreI18n.setLang,
          writable: false,
          configurable: true,
        });
      } catch (e) {
        window.setLang = window.LiftCoreI18n.setLang;
      }
      window.LiftCoreI18n.apply(lang);
    }
  }
  boot();
  window.addEventListener('load', boot);
})();
