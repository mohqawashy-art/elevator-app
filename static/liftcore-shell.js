(function () {
  'use strict';

  var HEADER_H_MIN = 104;

  function measureHeaderHeight(header) {
    if (!header) return HEADER_H_MIN;
    var h = header.getBoundingClientRect().height || header.offsetHeight || 0;
    return Math.max(HEADER_H_MIN, Math.ceil(h));
  }

  function applyHeaderHeight(header) {
    var h = measureHeaderHeight(header);
    document.documentElement.style.setProperty('--lc-header-h', h + 'px');
    applyNavHeight();
    return h;
  }

  function applyNavHeight() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar || !isDesktopTopNav()) {
      document.documentElement.style.setProperty('--lc-nav-h', '0px');
      document.documentElement.style.setProperty('--lc-top-stack-h', 'var(--lc-header-h, 104px)');
      return 0;
    }
    var navH = Math.ceil(sidebar.getBoundingClientRect().height || sidebar.offsetHeight || 0);
    document.documentElement.style.setProperty('--lc-nav-h', navH + 'px');
    var headerH = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--lc-header-h'), 10) || HEADER_H_MIN;
    document.documentElement.style.setProperty('--lc-top-stack-h', (headerH + navH) + 'px');
    return navH;
  }

  function isDesktopTopNav() {
    return window.matchMedia('(min-width: 1101px)').matches;
  }

  function findAppHeader() {
    return document.querySelector('body > header.lc-header, body > .lc-header') ||
      document.querySelector('.main .lc-header, .main > header.header');
  }

  function mountTopNavShell() {
    var sidebar = document.getElementById('sidebar');
    var main = document.querySelector('.main');
    var header = document.querySelector('.main .lc-header, .main > header.header');
    if (!sidebar || !main || !header || header.dataset.lcShellMounted === '1') return;
    sidebar.parentNode.insertBefore(header, sidebar);
    header.dataset.lcShellMounted = '1';
    document.documentElement.classList.add('lc-shell-ready');
    applyHeaderHeight(header);
  }

  function unmountTopNavShell() {
    var header = document.querySelector('body > header.lc-header, body > .lc-header');
    var main = document.querySelector('.main');
    if (!header || !main || header.dataset.lcShellMounted !== '1') return;
    main.insertBefore(header, main.firstChild);
    header.dataset.lcShellMounted = '0';
    document.documentElement.classList.remove('lc-shell-ready');
  }

  function applyTopNavShell() {
    if (isDesktopTopNav()) {
      if (!document.querySelector('body > header.lc-header, body > .lc-header')) {
        mountTopNavShell();
      } else {
        document.documentElement.classList.add('lc-shell-ready');
      }
    } else {
      unmountTopNavShell();
    }
    syncTopNavLayout();
  }

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
    if (isDesktopTopNav()) return;
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
        scrollNavItemIntoView(a);
      });
    });
    highlightActiveNav();
  }

  function scrollNavItemIntoView(link) {
    if (!link || !isDesktopTopNav()) return;
    var nav = link.closest('.sidebar-nav') || document.getElementById('sidebar');
    if (!nav) return;
    try {
      link.scrollIntoView({ behavior: 'smooth', inline: 'nearest', block: 'nearest' });
    } catch (e) {
      link.scrollIntoView(false);
    }
  }

  function highlightActiveNav() {
    var path = (location.pathname || '').replace(/\/+$/, '') || '/';
    document.querySelectorAll('#sidebar .nav-item[href], .sidebar .nav-item[href]').forEach(function (a) {
      var href = (a.getAttribute('href') || '').replace(/\/+$/, '') || '/';
      var active = href === path || (href !== '/' && path.indexOf(href) === 0);
      a.classList.toggle('active', active);
      if (active) scrollNavItemIntoView(a);
    });
  }

  function syncTopNavLayout() {
    var header = findAppHeader();
    if (!header) return;

    document.documentElement.classList.add('lc-layout-topnav');

    if (!isDesktopTopNav()) return;

    applyHeaderHeight(header);
  }

  function bindSidebarLayout() {
    applyTopNavShell();
    requestAnimationFrame(function () {
      requestAnimationFrame(applyTopNavShell);
    });
    window.addEventListener('resize', applyTopNavShell);
    var header = findAppHeader();
    if (header && window.ResizeObserver) {
      var ro = new ResizeObserver(function () { applyHeaderHeight(header); });
      ro.observe(header);
    }
    var sidebar = document.getElementById('sidebar');
    if (sidebar && window.ResizeObserver) {
      var navRo = new ResizeObserver(function () { applyNavHeight(); });
      navRo.observe(sidebar);
    }
    document.querySelectorAll('.lc-header-tenant-logo, .lc-header-logo').forEach(function (img) {
      if (img.complete) return;
      img.addEventListener('load', function () { applyHeaderHeight(findAppHeader()); });
    });
  }

  window.syncTopNavLayout = syncTopNavLayout;
  window.applyTopNavShell = applyTopNavShell;
  window.applyHeaderHeight = applyHeaderHeight;
  window.applyNavHeight = applyNavHeight;

  document.addEventListener('fullscreenchange', updateFullscreenIcon);
  document.addEventListener('webkitfullscreenchange', updateFullscreenIcon);

  document.addEventListener('DOMContentLoaded', function () {
    updateFullscreenIcon();
    bindSidebarNav();
    bindSidebarLayout();
    if (window.LiftCoreFormat) {
      LiftCoreFormat.initHeaderDates();
      if (typeof LiftCoreFormat.applyWesternDigits === 'function') {
        LiftCoreFormat.applyWesternDigits(document.body);
      }
    }
  });

  document.addEventListener('liftcore:live-sync', syncTopNavLayout);
  document.addEventListener('liftcore:display-refresh', syncTopNavLayout);
})();
