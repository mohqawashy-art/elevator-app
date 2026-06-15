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

  document.addEventListener('fullscreenchange', updateFullscreenIcon);
  document.addEventListener('webkitfullscreenchange', updateFullscreenIcon);

  function isListToolbarNode(el) {
    if (!el || !el.classList) return false;
    return el.classList.contains('page-header') || el.classList.contains('filters-bar');
  }

  function isSkippableBeforeToolbar(el) {
    if (!el || el.nodeType !== 1) return false;
    if (isListToolbarNode(el)) return false;
    if (el.classList.contains('tabs')) return false;
    if (el.classList.contains('table-wrap')) return false;
    if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE') return true;
    if (el.classList.contains('alert-expired') || el.classList.contains('alert-expiry')) return true;
    return el.tagName === 'DIV' && !el.classList.contains('lc-sticky-list-head');
  }

  function findTableWrapForZone(zone) {
    var el = zone.nextElementSibling;
    while (el) {
      if (el.classList && el.classList.contains('table-wrap') && !el.closest('.modal')) return el;
      var tw = el.querySelector && el.querySelector('.table-wrap:not(.modal .table-wrap)');
      if (tw && !tw.closest('.modal') && tw.id !== 'import-table-wrap') return tw;
      el = el.nextElementSibling;
    }
    return null;
  }

  function syncStickyTheadTop(zone, tableWrap) {
    if (!zone || !tableWrap) return;
    var h = zone.getBoundingClientRect().height;
    tableWrap.style.setProperty('--lc-thead-top', Math.ceil(h) + 'px');
  }

  function syncTabStickyToolbar() {
    document.querySelectorAll('.content .lc-sticky-list-head .lc-sticky-list-toolbar').forEach(function (toolbar) {
      var zone = toolbar.closest('.lc-sticky-list-head');
      if (!zone) return;
      var tabPanel = zone.nextElementSibling;
      while (tabPanel && tabPanel.id !== 'tab-table') {
        tabPanel = tabPanel.nextElementSibling;
      }
      if (!tabPanel) {
        toolbar.style.display = '';
        return;
      }
      toolbar.style.display = tabPanel.style.display === 'none' ? 'none' : '';
      var tw = tabPanel.querySelector('.table-wrap.lc-sticky-table-wrap');
      if (zone && tw) {
        requestAnimationFrame(function () {
          syncStickyTheadTop(zone, tw);
        });
      }
    });
  }

  function wrapStickyListToolbar(tableWrap) {
    if (tableWrap.dataset.lcStickyDone || tableWrap.closest('.modal') || tableWrap.id === 'import-table-wrap') {
      return null;
    }
    if (!tableWrap.closest('.content')) return null;

    var panel = tableWrap.parentElement;
    var toolbarNodes = [];
    var node = tableWrap.previousElementSibling;
    while (node) {
      if (isListToolbarNode(node)) {
        toolbarNodes.unshift(node);
        node = node.previousElementSibling;
        continue;
      }
      if (isSkippableBeforeToolbar(node)) {
        node = node.previousElementSibling;
        continue;
      }
      break;
    }
    if (!toolbarNodes.length) return null;

    var tabs = null;
    if (panel && panel.parentElement) {
      var prev = panel.previousElementSibling;
      if (prev && prev.classList.contains('tabs')) tabs = prev;
    }

    var insertParent = tabs ? panel.parentElement : panel;
    var insertBefore = tabs || toolbarNodes[0];
    var zone = document.createElement('div');
    zone.className = 'lc-sticky-list-head';
    insertParent.insertBefore(zone, insertBefore);

    if (tabs) zone.appendChild(tabs);

    var target = zone;
    if (tabs) {
      var toolbarWrap = document.createElement('div');
      toolbarWrap.className = 'lc-sticky-list-toolbar';
      zone.appendChild(toolbarWrap);
      target = toolbarWrap;
    }

    toolbarNodes.forEach(function (n) {
      target.appendChild(n);
    });

    tableWrap.classList.add('lc-sticky-table-wrap');
    tableWrap.dataset.lcStickyDone = '1';
    syncStickyTheadTop(zone, tableWrap);
    return zone;
  }

  function initListStickyHead() {
    document.querySelectorAll('.content .table-wrap').forEach(function (tw) {
      if (tw.classList.contains('lc-sticky-table-wrap') || tw.dataset.lcStickyDone) return;
      wrapStickyListToolbar(tw);
    });

    document.querySelectorAll('.content .lc-sticky-list-head').forEach(function (zone) {
      var tw = findTableWrapForZone(zone);
      if (tw) {
        tw.classList.add('lc-sticky-table-wrap');
        tw.dataset.lcStickyDone = '1';
        syncStickyTheadTop(zone, tw);
      }
    });

    syncTabStickyToolbar();
  }

  window.lcSyncStickyListHead = initListStickyHead;

  document.addEventListener('DOMContentLoaded', function () {
    updateFullscreenIcon();
    bindSidebarNav();
    initListStickyHead();

    var tabTable = document.getElementById('tab-table');
    if (tabTable && window.MutationObserver) {
      new MutationObserver(function () {
        syncTabStickyToolbar();
      }).observe(tabTable, { attributes: true, attributeFilter: ['style', 'class'] });
    }

    if (window.ResizeObserver) {
      var ro = new ResizeObserver(function () {
        document.querySelectorAll('.content .lc-sticky-list-head').forEach(function (zone) {
          var tw = findTableWrapForZone(zone);
          if (tw) syncStickyTheadTop(zone, tw);
        });
      });
      document.querySelectorAll('.content .lc-sticky-list-head').forEach(function (zone) {
        ro.observe(zone);
      });
    }

    window.addEventListener('resize', function () {
      document.querySelectorAll('.content .lc-sticky-list-head').forEach(function (zone) {
        var tw = findTableWrapForZone(zone);
        if (tw) syncStickyTheadTop(zone, tw);
      });
    });

    if (window.LiftCoreFormat) {
      LiftCoreFormat.initHeaderDates();
      LiftCoreFormat.applyWesternDigits(document.body);
    }
  });

  window.addEventListener('load', initListStickyHead);
})();
