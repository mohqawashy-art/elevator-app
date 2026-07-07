/**
 * LiftCore — تجميد الجزء العلوي حتى رأس الجدول في كل صفحة قائمة
 */
(function (global) {
  'use strict';

  function isReportPage() {
    var b = document.body;
    if (!b) return false;
    return !!(b.getAttribute('data-report-id')
      || b.getAttribute('data-report-dashboard')
      || b.getAttribute('data-report-annual'));
  }

  function isMobileViewport() {
    return !!(global.matchMedia && global.matchMedia('(max-width: 1100px)').matches);
  }

  function canFreezeLayout(content) {
    if (isMobileViewport()) return false;
    if (isReportPage()) return false;
    if (content.querySelector('.print-wrap')) return false;
    if (!content.querySelector('.table-wrap')) return false;
    if (content.querySelector('.kpi-grid')) return false;
    if (content.querySelector('.charts-2')) return false;
    if (content.querySelector('.chart-card canvas')) return false;
    return true;
  }

  function isHiddenTabPanel(el) {
    if (!el || !el.style) return false;
    return el.style.display === 'none';
  }

  function isTableWrapCandidate(wrap) {
    if (!wrap || wrap.classList.contains('lc-sticky-skip')) return false;
    var node = wrap.parentElement;
    while (node) {
      if (node.id === 'tab-teams' || node.id === 'tab-table') {
        if (isHiddenTabPanel(node)) return false;
      }
      if (node.classList && node.classList.contains('content')) break;
      node = node.parentElement;
    }
    return true;
  }

  function getPrimaryTableWrap(content) {
    var wraps = content.querySelectorAll('.table-wrap');
    var candidate = null;
    for (var i = 0; i < wraps.length; i++) {
      if (isTableWrapCandidate(wraps[i])) candidate = wraps[i];
    }
    return candidate;
  }

  function collectAboveTable(tableWrap, content) {
    var items = [];
    var el = tableWrap;
    while (el && el !== content) {
      var prev = el.previousElementSibling;
      while (prev) {
        items.unshift(prev);
        prev = prev.previousElementSibling;
      }
      el = el.parentElement;
    }
    return items;
  }

  function measureStack(content, stack) {
    if (!stack) {
      content.style.setProperty('--lc-sticky-stack-h', '0px');
      return;
    }
    content.style.setProperty('--lc-sticky-stack-h', Math.ceil(stack.getBoundingClientRect().height) + 'px');
  }

  function initContent(content) {
    if (!content || content.dataset.lcStickyInit) return;
    if (isReportPage()) return;
    if (isMobileViewport()) {
      content.classList.remove('lc-frozen-layout');
    }

    var tableWrap = getPrimaryTableWrap(content);
    if (!tableWrap) return;

    content.dataset.lcStickyInit = '1';
    tableWrap.classList.add('lc-table-scroll-host');

    var above = collectAboveTable(tableWrap, content);
    var stack = content.querySelector('.lc-page-sticky-top');

    if (!stack && above.length) {
      stack = document.createElement('div');
      stack.className = 'lc-page-sticky-top';
      tableWrap.parentNode.insertBefore(stack, tableWrap);
      above.forEach(function (node) {
        stack.appendChild(node);
      });
    }

    if (canFreezeLayout(content)) {
      content.classList.add('lc-frozen-layout');
    }

    measureStack(content, stack);

    if (stack && global.ResizeObserver) {
      new ResizeObserver(function () {
        measureStack(content, stack);
      }).observe(stack);
    }
  }

  function refreshHeights() {
    document.querySelectorAll('.content[data-lc-sticky-init]').forEach(function (content) {
      measureStack(content, content.querySelector('.lc-page-sticky-top'));
    });
  }

  function initAll() {
    document.querySelectorAll('.content').forEach(initContent);
    refreshHeights();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  global.addEventListener('resize', function () {
    if (isMobileViewport()) {
      document.querySelectorAll('.content.lc-frozen-layout').forEach(function (content) {
        content.classList.remove('lc-frozen-layout');
      });
    }
    refreshHeights();
  });
  document.addEventListener('liftcore:lang', function () {
    setTimeout(refreshHeights, 80);
  });

  global.LiftCoreStickyTop = { refresh: refreshHeights, init: initAll };
})(typeof window !== 'undefined' ? window : this);
