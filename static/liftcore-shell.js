(function () {
  'use strict';

  function updateFullscreenIcon() {
    var btn = document.getElementById('btn-fullscreen');
    if (!btn) return;
    var on = !!document.fullscreenElement;
    var enter = btn.querySelector('.lc-fs-enter');
    var exit = btn.querySelector('.lc-fs-exit');
    if (enter) enter.style.display = on ? 'none' : '';
    if (exit) exit.style.display = on ? '' : 'none';
    var titleKey = on ? 'fullscreen_exit' : 'fullscreen';
    btn.setAttribute('data-i18n-title', titleKey);
    if (window.LiftCoreI18n && window.LiftCoreI18n.KEYS && window.LiftCoreI18n.KEYS[titleKey]) {
      var lang = document.documentElement.getAttribute('lang') || 'ar';
      btn.setAttribute('title', window.LiftCoreI18n.KEYS[titleKey][lang]);
    }
    document.documentElement.classList.toggle('lc-fullscreen', on);
  }

  window.toggleFullscreen = function () {
    var el = document.documentElement;
    if (!document.fullscreenElement) {
      var req = el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen;
      if (req) {
        Promise.resolve(req.call(el)).catch(function () { /* denied */ });
      }
    } else {
      var exit = document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen;
      if (exit) exit.call(document);
    }
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

  window.openSidebar = function () {
    if (window.matchMedia('(min-width: 1101px)').matches) return;
    var sidebar = document.getElementById('sidebar');
    var overlay = document.getElementById('overlay');
    if (sidebar) sidebar.classList.add('open');
    if (overlay) overlay.classList.add('open');
  };

  window.closeSidebar = function () {
    var sidebar = document.getElementById('sidebar');
    var overlay = document.getElementById('overlay');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('open');
  };

  function bindSidebarNav() {
    document.querySelectorAll('#sidebar .nav-item[href], .sidebar .nav-item[href]').forEach(function (a) {
      if (a.dataset.lcNavBound) return;
      a.dataset.lcNavBound = '1';
      a.addEventListener('click', function () {
        window.closeSidebar();
      });
    });
  }

  function syncTopNavLayout() {
    var sidebar = document.getElementById('sidebar');
    var main = document.querySelector('.main');
    if (!sidebar || !main) return;

    document.documentElement.classList.add('lc-layout-topnav');

    if (window.matchMedia('(max-width: 1100px)').matches) return;

    var header = main.querySelector('.lc-header, .header');
    var headerH = header ? header.offsetHeight : 75;
    document.documentElement.style.setProperty('--lc-header-h', headerH + 'px');
  }

  function bindSidebarLayout() {
    syncTopNavLayout();
    requestAnimationFrame(function () {
      requestAnimationFrame(syncTopNavLayout);
    });
    window.addEventListener('resize', syncTopNavLayout);
    var main = document.querySelector('.main');
    if (!main || !window.ResizeObserver) return;
    var ro = new ResizeObserver(function () { syncTopNavLayout(); });
    ro.observe(main);
    var header = main.querySelector('.lc-header, .header');
    if (header) ro.observe(header);
  }

  window.syncTopNavLayout = syncTopNavLayout;

  document.addEventListener('fullscreenchange', updateFullscreenIcon);
  document.addEventListener('webkitfullscreenchange', updateFullscreenIcon);

  document.addEventListener('DOMContentLoaded', function () {
    updateFullscreenIcon();
    bindSidebarNav();
    bindSidebarLayout();
    if (window.LiftCoreFormat) {
      LiftCoreFormat.initHeaderDates();
      LiftCoreFormat.applyWesternDigits(document.body);
    }
  });

  document.addEventListener('liftcore:live-sync', syncTopNavLayout);
  document.addEventListener('liftcore:display-refresh', syncTopNavLayout);
})();
