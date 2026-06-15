(function () {
  'use strict';

  var WELCOME_KEY = 'lc_welcome_date';
  var SIDEBAR_KEY = 'lc_sidebar_compact';
  var FS_SESSION_KEY = 'lc_session_fullscreen';

  function metaContent(name) {
    var el = document.querySelector('meta[name="' + name + '"]');
    return el ? el.getAttribute('content') || '' : '';
  }

  function todayKey() {
    var d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  function t(key, fallback) {
    if (window.LiftCoreI18n && window.LiftCoreI18n.KEYS && window.LiftCoreI18n.KEYS[key]) {
      var lang = document.documentElement.getAttribute('lang') || 'ar';
      return window.LiftCoreI18n.KEYS[key][lang] || fallback;
    }
    return fallback;
  }

  function updateFullscreenIcon() {
    var btn = document.getElementById('btn-fullscreen');
    var on = !!document.fullscreenElement;
    if (btn) {
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
    }
    document.documentElement.classList.toggle('lc-fullscreen', on);
  }

  function enterFullscreen() {
    var el = document.documentElement;
    if (document.fullscreenElement) return Promise.resolve();
    var req = el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen;
    if (!req) return Promise.resolve();
    return Promise.resolve(req.call(el)).catch(function () { /* denied */ });
  }

  window.toggleFullscreen = function () {
    if (!document.fullscreenElement) {
      try { sessionStorage.setItem(FS_SESSION_KEY, '1'); } catch (e) { /* ignore */ }
      enterFullscreen();
      return;
    }
    try { sessionStorage.removeItem(FS_SESSION_KEY); } catch (e) { /* ignore */ }
    var exit = document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen;
    if (exit) exit.call(document);
  };

  function restoreSessionFullscreen() {
    try {
      if (sessionStorage.getItem(FS_SESSION_KEY) !== '1') return;
    } catch (e) { return; }
    if (document.fullscreenElement) return;
    enterFullscreen();
  }

  function onFullscreenChange() {
    updateFullscreenIcon();
  }

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

  function cacheNavLabels() {
    document.querySelectorAll('#sidebar .nav-item[href], .sidebar .nav-item[href]').forEach(function (a) {
      if (a.dataset.lcNavLabel) return;
      var clone = a.cloneNode(true);
      clone.querySelectorAll('svg, .nav-badge').forEach(function (n) { n.remove(); });
      var label = clone.textContent.replace(/\s+/g, ' ').trim();
      if (label) a.dataset.lcNavLabel = label;
    });
  }

  function syncNavTitles() {
    var compact = document.documentElement.classList.contains('lc-sidebar-compact');
    document.querySelectorAll('#sidebar .nav-item[href], .sidebar .nav-item[href]').forEach(function (a) {
      if (compact && a.dataset.lcNavLabel) {
        a.setAttribute('title', a.dataset.lcNavLabel);
      } else {
        a.removeAttribute('title');
      }
    });
  }

  window.toggleSidebarCompact = function () {
    var root = document.documentElement;
    var next = !root.classList.contains('lc-sidebar-compact');
    root.classList.toggle('lc-sidebar-compact', next);
    try { localStorage.setItem(SIDEBAR_KEY, next ? '1' : '0'); } catch (e) { /* ignore */ }
    syncNavTitles();
    var btn = document.getElementById('lc-sidebar-toggle');
    if (btn) {
      btn.setAttribute('aria-expanded', next ? 'false' : 'true');
      btn.setAttribute('title', next ? t('sidebar_expand', 'فتح القائمة') : t('sidebar_collapse', 'طي القائمة'));
    }
  };

  function initSidebarToggle() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar || sidebar.querySelector('.lc-sidebar-toggle')) return;

    cacheNavLabels();

    try {
      if (localStorage.getItem(SIDEBAR_KEY) === '1' && window.innerWidth > 768) {
        document.documentElement.classList.add('lc-sidebar-compact');
      }
    } catch (e) { /* ignore */ }

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'lc-sidebar-toggle';
    btn.id = 'lc-sidebar-toggle';
    btn.setAttribute('aria-label', t('sidebar_toggle', 'طي/فتح القائمة'));
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>';
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      window.toggleSidebarCompact();
    });
    sidebar.appendChild(btn);

    var compact = document.documentElement.classList.contains('lc-sidebar-compact');
    btn.setAttribute('aria-expanded', compact ? 'false' : 'true');
    btn.setAttribute('title', compact ? t('sidebar_expand', 'فتح القائمة') : t('sidebar_collapse', 'طي القائمة'));
    syncNavTitles();
  }

  function dismissWelcome(splash) {
    if (!splash) return;
    splash.classList.add('lc-welcome-hide');
    setTimeout(function () {
      if (splash.parentNode) splash.parentNode.removeChild(splash);
    }, 600);
    try { localStorage.setItem(WELCOME_KEY, todayKey()); } catch (e) { /* ignore */ }
  }

  function initWelcomeSplash() {
    if (!document.getElementById('sidebar') || !metaContent('lc-brand-logo')) return;
    try {
      if (localStorage.getItem(WELCOME_KEY) === todayKey()) return;
    } catch (e) { /* ignore */ }

    var brandLogo = metaContent('lc-brand-logo');
    var productLogo = metaContent('lc-product-logo');
    var brandName = metaContent('lc-brand-name') || 'LiftCore';
    var userName = metaContent('lc-user-name');

    var splash = document.createElement('div');
    splash.id = 'lc-welcome-splash';
    splash.className = 'lc-welcome-splash';
    splash.setAttribute('role', 'dialog');
    splash.setAttribute('aria-modal', 'true');
    splash.setAttribute('aria-label', t('welcome_title', 'مرحباً بك'));

    var title = userName
      ? t('welcome_title_user', 'مرحباً، ') + userName
      : t('welcome_title', 'مرحباً بك في ') + brandName;

    splash.innerHTML =
      '<div class="lc-welcome-bg"></div>' +
      '<div class="lc-welcome-content">' +
        '<div class="lc-welcome-logo-wrap">' +
          '<img class="lc-welcome-logo" src="' + brandLogo + '" alt="' + brandName + '">' +
        '</div>' +
        (productLogo ? '<img class="lc-welcome-product" src="' + productLogo + '" alt="LiftCore">' : '') +
        '<h1 class="lc-welcome-title">' + title + '</h1>' +
        '<p class="lc-welcome-sub">' + t('welcome_sub', 'نظام إدارة المصاعد — جاهز للعمل') + '</p>' +
        '<button type="button" class="lc-welcome-start" id="lc-welcome-start">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 00-2 2v3M16 3h3a2 2 0 012 2v3M8 21H5a2 2 0 01-2-2v-3M16 21h3a2 2 0 002-2v-3"/></svg>' +
          '<span>' + t('welcome_start', 'ابدأ') + '</span>' +
        '</button>' +
      '</div>';

    document.body.appendChild(splash);

    var startBtn = document.getElementById('lc-welcome-start');
    if (startBtn) {
      startBtn.addEventListener('click', function () {
        dismissWelcome(splash);
        try { sessionStorage.setItem(FS_SESSION_KEY, '1'); } catch (e) { /* ignore */ }
        enterFullscreen();
      });
    }
  }

  document.addEventListener('fullscreenchange', onFullscreenChange);
  document.addEventListener('webkitfullscreenchange', onFullscreenChange);

  document.addEventListener('DOMContentLoaded', function () {
    updateFullscreenIcon();
    bindSidebarNav();
    initSidebarToggle();
    initWelcomeSplash();
    restoreSessionFullscreen();
    if (window.LiftCoreFormat) {
      LiftCoreFormat.initHeaderDates();
      LiftCoreFormat.applyWesternDigits(document.body);
    }
  });
})();
