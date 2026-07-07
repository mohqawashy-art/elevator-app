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

  function isMobileViewport() {
    return !isDesktopTopNav();
  }

  function unfreezeMobileContent() {
    document.querySelectorAll('.content.lc-frozen-layout').forEach(function (el) {
      el.classList.remove('lc-frozen-layout');
    });
  }

  function syncMobileHeaderHeight() {
    if (!isMobileViewport()) {
      document.documentElement.style.removeProperty('--lc-header-h');
      return;
    }
    var header = findAppHeader();
    if (!header) return;
    var h = Math.max(52, Math.ceil(header.getBoundingClientRect().height || header.offsetHeight || 0));
    document.documentElement.style.setProperty('--lc-header-h', h + 'px');
  }

  function syncMobileScroll() {
    var mobile = isMobileViewport();
    document.documentElement.classList.toggle('lc-mobile-scroll', mobile);
    document.documentElement.classList.toggle('lc-mobile-native', mobile);
    if (document.body) document.body.classList.toggle('lc-mobile-native', mobile);
    if (mobile) {
      unfreezeMobileContent();
      requestAnimationFrame(function () {
        syncMobileHeaderHeight();
        if (window.LiftCoreMobileTouch && window.LiftCoreMobileTouch.refresh) {
          window.LiftCoreMobileTouch.refresh();
        }
      });
    } else {
      document.documentElement.style.removeProperty('--lc-header-h');
    }
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
    syncMobileScroll();
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

  function resetNavGroupMenuPosition(group) {
    var menu = group.querySelector('.nav-group-menu');
    if (!menu) return;
    menu.classList.remove('nav-group-menu-fixed');
    menu.style.top = '';
    menu.style.left = '';
    menu.style.right = '';
    menu.style.minWidth = '';
  }

  function positionNavGroupMenu(group) {
    if (!isDesktopTopNav() || !group.classList.contains('open')) {
      resetNavGroupMenuPosition(group);
      return;
    }
    var menu = group.querySelector('.nav-group-menu');
    var btn = group.querySelector('.nav-group-btn');
    if (!menu || !btn) return;
    var rect = btn.getBoundingClientRect();
    menu.classList.add('nav-group-menu-fixed');
    menu.style.top = Math.round(rect.bottom + 4) + 'px';
    menu.style.minWidth = Math.max(210, Math.round(rect.width)) + 'px';
    var dir = document.documentElement.getAttribute('dir') || 'rtl';
    if (dir === 'ltr') {
      menu.style.left = Math.round(rect.left) + 'px';
      menu.style.right = 'auto';
    } else {
      menu.style.right = Math.round(window.innerWidth - rect.right) + 'px';
      menu.style.left = 'auto';
    }
  }

  function repositionOpenNavGroups() {
    document.querySelectorAll('[data-nav-group].open').forEach(positionNavGroupMenu);
  }

  function closeAllNavGroups(except) {
    document.querySelectorAll('[data-nav-group]').forEach(function (g) {
      if (except && g === except) return;
      g.classList.remove('open');
      var btn = g.querySelector('.nav-group-btn');
      if (btn) btn.setAttribute('aria-expanded', 'false');
      resetNavGroupMenuPosition(g);
    });
  }

  function bindNavGroups() {
    document.querySelectorAll('[data-nav-group]').forEach(function (group) {
      if (group.dataset.lcNavGroupBound) return;
      group.dataset.lcNavGroupBound = '1';
      var btn = group.querySelector('.nav-group-btn');
      if (!btn) return;
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var willOpen = !group.classList.contains('open');
        closeAllNavGroups(willOpen ? group : null);
        group.classList.toggle('open', willOpen);
        btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
        if (willOpen) {
          requestAnimationFrame(function () { positionNavGroupMenu(group); });
        } else {
          resetNavGroupMenuPosition(group);
        }
      });
    });
    if (!document.documentElement.dataset.lcNavGroupDocBound) {
      document.documentElement.dataset.lcNavGroupDocBound = '1';
      document.addEventListener('click', function (e) {
        if (e.target.closest('[data-nav-group]')) return;
        closeAllNavGroups();
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeAllNavGroups();
      });
      window.addEventListener('resize', repositionOpenNavGroups);
      window.addEventListener('scroll', repositionOpenNavGroups, true);
    }
  }

  function bindSidebarNav() {
    bindNavGroups();
    document.querySelectorAll('#sidebar .nav-item[href], .sidebar .nav-item[href]').forEach(function (a) {
      if (a.dataset.lcNavBound) return;
      a.dataset.lcNavBound = '1';
      a.addEventListener('click', function () {
        closeAllNavGroups();
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

  function matchNavHref(linkHref) {
    var raw = (linkHref || '').split('#')[0];
    var q = raw.indexOf('?');
    var hrefPath = (q >= 0 ? raw.slice(0, q) : raw).replace(/\/+$/, '') || '/';
    var hrefQuery = q >= 0 ? raw.slice(q) : '';
    var path = (location.pathname || '').replace(/\/+$/, '') || '/';
    var search = location.search || '';
    if (hrefQuery) return hrefPath === path && hrefQuery === search;
    if (hrefPath === path) return !search;
    return hrefPath !== '/' && path.indexOf(hrefPath) === 0;
  }

  function highlightActiveNav() {
    document.querySelectorAll('[data-nav-group]').forEach(function (group) {
      group.classList.remove('has-active');
    });
    document.querySelectorAll('#sidebar .nav-item[href], .sidebar .nav-item[href]').forEach(function (a) {
      var active = matchNavHref(a.getAttribute('href'));
      a.classList.toggle('active', active);
      if (active) {
        var group = a.closest('[data-nav-group]');
        if (group) {
          group.classList.add('has-active');
          if (!isDesktopTopNav()) group.classList.add('open');
        }
        scrollNavItemIntoView(a);
      }
    });
    document.querySelectorAll('#sidebar .nav-item-single[href], .sidebar .nav-item-single[href]').forEach(function (a) {
      var active = matchNavHref(a.getAttribute('href'));
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

  window.syncMobileScroll = syncMobileScroll;
  window.syncTopNavLayout = syncTopNavLayout;
  window.applyTopNavShell = applyTopNavShell;
  window.applyHeaderHeight = applyHeaderHeight;
  window.applyNavHeight = applyNavHeight;

  document.addEventListener('fullscreenchange', updateFullscreenIcon);
  document.addEventListener('webkitfullscreenchange', updateFullscreenIcon);

  function syncDeviceClass() {
    var w = window.innerWidth || document.documentElement.clientWidth || 0;
    var root = document.documentElement;
    root.classList.remove('lc-device-phone', 'lc-device-tablet', 'lc-device-desktop');
    if (w <= 767) root.classList.add('lc-device-phone');
    else if (w <= 1100) root.classList.add('lc-device-tablet');
    else root.classList.add('lc-device-desktop');
  }

  window.syncDeviceClass = syncDeviceClass;

  document.addEventListener('DOMContentLoaded', function () {
    syncDeviceClass();
    syncMobileScroll();
    window.addEventListener('resize', syncMobileScroll);
    window.addEventListener('resize', syncDeviceClass);
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

  function ensureToastHost() {
    var host = document.getElementById('lc-toast-host');
    if (host) return host;
    host = document.createElement('div');
    host.id = 'lc-toast-host';
    host.setAttribute('aria-live', 'polite');
    document.body.appendChild(host);
    return host;
  }

  function toast(message, opts) {
    opts = opts || {};
    var host = ensureToastHost();
    var el = document.createElement('div');
    el.className = 'lc-toast' + (opts.type ? ' lc-toast-' + opts.type : '');
    el.textContent = message || '';
    host.appendChild(el);
    var ms = opts.duration || 3200;
    setTimeout(function () {
      el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 250);
    }, ms);
    return el;
  }

  window.LiftCoreToast = toast;
})();
