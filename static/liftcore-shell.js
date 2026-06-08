(function () {
  'use strict';

  window.setLang = window.setLang || function (l) {
    document.documentElement.setAttribute('lang', l);
    document.documentElement.setAttribute('dir', l === 'ar' ? 'rtl' : 'ltr');
    var ar = document.getElementById('btn-ar');
    var en = document.getElementById('btn-en');
    if (ar) ar.classList.toggle('active', l === 'ar');
    if (en) en.classList.toggle('active', l === 'en');
  };

  window.toggleProfileMenu = function (e) {
    if (e) e.stopPropagation();
    var menu = document.getElementById('profile-dropdown');
    if (!menu) return;
    menu.classList.toggle('open');
  };

  document.addEventListener('click', function () {
    var menu = document.getElementById('profile-dropdown');
    if (menu) menu.classList.remove('open');
  });

  document.addEventListener('DOMContentLoaded', function () {
    if (window.LiftCoreFormat) {
      LiftCoreFormat.initHeaderDates();
      LiftCoreFormat.applyWesternDigits(document.body);
    }
  });
})();
