/**
 * LiftCore — اختصارات لوحة المفاتيح (F1–F12)
 *
 * F1     = إضافة حسب الصفحة الحالية
 * F2–F4, F6–F9 = انتقال سريع لإضافة في وحدة أخرى
 * F5     = تحديث الصفحة (سلوك المتصفح — لا نلتقطه)
 * F10    = بحث
 * F11/?  = مساعدة
 * F12    = طباعة
 */
(function (global) {
  'use strict';

  var PAGE_ADD = [
    { path: '/clients', label: 'إضافة عميل', addFn: 'openAddModal' },
    { path: '/elevators', label: 'إضافة مصعد', addFn: 'openAddModal' },
    { path: '/contracts', label: 'إضافة عقد', addFn: 'openAddModal' },
    { path: '/faults', label: 'تسجيل عطل', addFn: 'openAddModal' },
    { path: '/maintenance-visits', label: 'جدولة زيارة', addFn: 'openAddModal' },
    { path: '/invoices', label: 'إنشاء فاتورة', addFn: 'openAddModal' },
    { path: '/revenues', label: 'تسجيل إيراد', addFn: 'openAddModal' },
    { path: '/expenses', label: 'إضافة مصروف', addFn: 'openModal' },
    { path: '/technicians', label: 'إضافة فني', addFn: 'openAddModal' },
    { path: '/inventory', label: 'إضافة صنف', addFn: 'openModal' },
    { path: '/parts-billing', label: 'إضافة فاتورة قطع', addFn: 'openModal' },
    { path: '/stock-movements', label: 'إضافة حركة مخزون', addFn: 'openModal' }
  ];

  var JUMP_KEYS = [
    { key: 'F2', path: '/elevators', label: 'إضافة مصعد' },
    { key: 'F3', path: '/contracts', label: 'إضافة عقد' },
    { key: 'F4', path: '/faults', label: 'تسجيل عطل' },
    { key: 'F6', path: '/invoices', label: 'إنشاء فاتورة' },
    { key: 'F7', path: '/revenues', label: 'تسجيل إيراد' },
    { key: 'F8', path: '/expenses', label: 'إضافة مصروف' },
    { key: 'F9', path: '/technicians', label: 'إضافة فني' }
  ];

  function pathname() {
    return (global.location.pathname || '').replace(/\/+$/, '') || '/';
  }

  function pathMatches(path) {
    var p = pathname();
    var target = (path || '').replace(/\/+$/, '') || '/';
    return p === target || p.indexOf(target + '/') === 0;
  }

  function currentPageAdd() {
    var i;
    for (i = 0; i < PAGE_ADD.length; i++) {
      if (pathMatches(PAGE_ADD[i].path)) return PAGE_ADD[i];
    }
    return null;
  }

  function pageByPath(path) {
    var i;
    for (i = 0; i < PAGE_ADD.length; i++) {
      if (PAGE_ADD[i].path === path) return PAGE_ADD[i];
    }
    return null;
  }

  function helpRows() {
    var page = currentPageAdd();
    var f1Label = page
      ? ('إضافة هنا: ' + page.label.replace(/^إضافة |^تسجيل |^إنشاء |^جدولة /, ''))
      : 'لا توجد إضافة في هذه الصفحة — يعرض المساعدة';
    var rows = [{ key: 'F1', label: f1Label }];
    JUMP_KEYS.forEach(function (j) {
      rows.push({ key: j.key, label: j.label });
    });
    rows.push(
      { key: 'F5', label: 'تحديث الصفحة' },
      { key: 'F10', label: 'البحث في الصفحة' },
      { key: 'F11', label: 'عرض الاختصارات' },
      { key: 'F12', label: 'طباعة' }
    );
    return rows;
  }

  function canWrite() {
    return global.__LC_CAN_WRITE !== false;
  }

  function isTypingTarget(el) {
    if (!el) return false;
    var tag = (el.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
    if (el.isContentEditable) return true;
    if (el.closest && el.closest('[contenteditable="true"]')) return true;
    return false;
  }

  function toast(msg) {
    if (typeof global.showToast === 'function') {
      try { global.showToast(msg); return; } catch (e) { /* fall through */ }
    }
    var existing = document.getElementById('lc-hotkey-toast');
    if (existing) existing.remove();
    var el = document.createElement('div');
    el.id = 'lc-hotkey-toast';
    el.className = 'lc-hotkey-toast';
    el.textContent = msg;
    document.body.appendChild(el);
    requestAnimationFrame(function () { el.classList.add('show'); });
    setTimeout(function () {
      el.classList.remove('show');
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 220);
    }, 1800);
  }

  function findPrimaryAddButton() {
    return document.querySelector(
      '.page-actions .btn-primary, .content-header .btn-primary, .page-header .btn-primary, button.btn-primary.btn-sm'
    );
  }

  function findPrintButtons() {
    return document.querySelectorAll(
      '#btn-print-contract, #view-print-btn, #btn-print-top, ' +
      'button[onclick*="printContract"], button[onclick*="printInvoice"], ' +
      'button[onclick*="printVisit"], button[onclick*="LiftCorePrint"], ' +
      'button[onclick*="printReport"], button[onclick*="LiftCorePrint.report"]'
    );
  }

  function invokePageAdd(page, keyLabel) {
    if (!canWrite()) {
      toast('صلاحية العرض فقط — لا يمكن الإضافة');
      return false;
    }
    if (!page) return false;

    if (pathMatches(page.path)) {
      var fn = global[page.addFn];
      if (typeof fn === 'function') {
        try {
          if (page.path === '/revenues') fn(null);
          else fn();
          toast(page.label + ' (' + keyLabel + ')');
          return true;
        } catch (e) { /* fall through */ }
      }
      var btn = findPrimaryAddButton();
      if (btn && !btn.disabled) {
        btn.click();
        toast(page.label + ' (' + keyLabel + ')');
        return true;
      }
      toast('لا يوجد إجراء إضافة في هذه الصفحة');
      return false;
    }

    global.location.href = page.path + '?action=add';
    return true;
  }

  function addOnCurrentPage() {
    var page = currentPageAdd();
    if (!page) {
      showHelp();
      return;
    }
    invokePageAdd(page, 'F1');
  }

  function jumpAdd(jump) {
    var page = pageByPath(jump.path);
    if (!page) {
      global.location.href = jump.path + '?action=add';
      return;
    }
    invokePageAdd(page, jump.key);
  }

  function focusSearch() {
    var selectors = [
      '#search-input',
      '#f-search',
      '#q',
      '#search',
      'input[type="search"]',
      'input[placeholder*="بحث"]',
      'input[placeholder*="Search"]',
      '.filters input[type="text"]',
      '.toolbar input[type="text"]'
    ];
    var i, el;
    for (i = 0; i < selectors.length; i++) {
      el = document.querySelector(selectors[i]);
      if (el && el.offsetParent !== null) {
        el.focus();
        if (typeof el.select === 'function') el.select();
        toast('البحث (F10)');
        return;
      }
    }
    toast('لا يوجد حقل بحث في هذه الصفحة');
  }

  function clickFirst(selectors) {
    var i, el;
    for (i = 0; i < selectors.length; i++) {
      el = document.querySelector(selectors[i]);
      if (el && el.offsetParent !== null && !el.disabled) {
        el.click();
        return true;
      }
    }
    return false;
  }

  function doPrint() {
    if (clickFirst([
      '.modal-overlay.open #btn-print-contract:not([style*="display: none"])',
      '.modal-overlay.open #view-print-btn:not([style*="display: none"])',
      '.modal-overlay.open button[onclick*="print"]',
      '#btn-print-contract:not([style*="display: none"])',
      '#view-print-btn:not([style*="display: none"])',
      '#btn-print-top:not([disabled])',
      'button[onclick*="printContract"]',
      'button[onclick*="printInvoice"]',
      'button[onclick*="printVisit"]',
      'button[onclick*="LiftCorePrint"]',
      'button[onclick*="printReport"]'
    ])) {
      toast('طباعة (F12)');
      return;
    }
    if (global.LiftCorePrint && typeof global.LiftCorePrint.report === 'function') {
      global.LiftCorePrint.report();
      toast('طباعة (F12)');
      return;
    }
    if (typeof global.printReport === 'function') {
      global.printReport();
      toast('طباعة (F12)');
      return;
    }
    global.print();
    toast('طباعة (F12)');
  }

  function ensureHelpPanel() {
    var panel = document.getElementById('lc-hotkeys-help');
    if (panel) return panel;
    panel = document.createElement('div');
    panel.id = 'lc-hotkeys-help';
    panel.className = 'lc-hotkeys-help';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-label', 'اختصارات لوحة المفاتيح');
    panel.innerHTML =
      '<div class="lc-hotkeys-card">' +
        '<div class="lc-hotkeys-head">' +
          '<strong>اختصارات لوحة المفاتيح</strong>' +
          '<button type="button" class="lc-hotkeys-close" aria-label="إغلاق">&times;</button>' +
        '</div>' +
        '<div class="lc-hotkeys-grid" id="lc-hotkeys-grid"></div>' +
        '<p class="lc-hotkeys-note">F1 يتغيّر حسب الصفحة. F5 لتحديث الصفحة. أثناء الكتابة في الحقول تتوقف الاختصارات.</p>' +
      '</div>';
    panel.addEventListener('click', function (e) {
      if (e.target === panel || (e.target.classList && e.target.classList.contains('lc-hotkeys-close'))) {
        hideHelp();
      }
    });
    document.body.appendChild(panel);
    return panel;
  }

  function renderHelpRows() {
    var grid = document.getElementById('lc-hotkeys-grid');
    if (!grid) return;
    grid.innerHTML = helpRows().map(function (a) {
      return '<div class="lc-hotkeys-row"><kbd>' + a.key + '</kbd><span>' + a.label + '</span></div>';
    }).join('');
  }

  function showHelp() {
    var panel = ensureHelpPanel();
    renderHelpRows();
    panel.classList.add('open');
  }

  function hideHelp() {
    var panel = document.getElementById('lc-hotkeys-help');
    if (panel) panel.classList.remove('open');
  }

  function toggleHelp() {
    var panel = document.getElementById('lc-hotkeys-help');
    if (panel && panel.classList.contains('open')) hideHelp();
    else showHelp();
  }

  function addHint(btn, key) {
    if (!btn || btn.dataset.lcHotkeyHint === key) return;
    btn.dataset.lcHotkeyHint = key;
    var title = (btn.getAttribute('title') || '').trim();
    if (title.indexOf(key) < 0) {
      btn.setAttribute('title', title ? title + ' · ' + key : key);
    }
    if (!btn.querySelector('.lc-kbd-hint')) {
      var kbd = document.createElement('span');
      kbd.className = 'lc-kbd-hint';
      kbd.textContent = key;
      btn.appendChild(kbd);
    } else {
      btn.querySelector('.lc-kbd-hint').textContent = key;
    }
  }

  function annotateButtons() {
    if (currentPageAdd()) {
      addHint(findPrimaryAddButton(), 'F1');
    }
    findPrintButtons().forEach(function (btn) {
      addHint(btn, 'F12');
    });
  }

  function onKeyDown(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    if (e.key === 'Escape') {
      var help = document.getElementById('lc-hotkeys-help');
      if (help && help.classList.contains('open')) {
        e.preventDefault();
        hideHelp();
      }
      return;
    }

    if (!e.key || e.key.indexOf('F') !== 0) {
      if (e.key === '?' && !isTypingTarget(e.target)) {
        e.preventDefault();
        toggleHelp();
      }
      return;
    }

    var key = e.key;
    var isHelpOrPrint = key === 'F11' || key === 'F12';
    if (!isHelpOrPrint && isTypingTarget(e.target)) return;

    if (key === 'F1') {
      e.preventDefault();
      e.stopPropagation();
      addOnCurrentPage();
      return;
    }

    var jump = null;
    var i;
    for (i = 0; i < JUMP_KEYS.length; i++) {
      if (JUMP_KEYS[i].key === key) {
        jump = JUMP_KEYS[i];
        break;
      }
    }
    if (jump) {
      e.preventDefault();
      e.stopPropagation();
      jumpAdd(jump);
      return;
    }

    if (key === 'F10') {
      e.preventDefault();
      e.stopPropagation();
      focusSearch();
      return;
    }
    if (key === 'F11') {
      e.preventDefault();
      e.stopPropagation();
      toggleHelp();
      return;
    }
    if (key === 'F12') {
      e.preventDefault();
      e.stopPropagation();
      doPrint();
    }
  }

  function init() {
    if (document.documentElement.dataset.lcHotkeysBound) return;
    document.documentElement.dataset.lcHotkeysBound = '1';
    document.addEventListener('keydown', onKeyDown, true);
    annotateButtons();
    // أزرار الطباعة داخل المودالات قد تُحقن لاحقاً
    setTimeout(annotateButtons, 800);
    global.LiftCoreHotkeys = {
      showHelp: showHelp,
      hideHelp: hideHelp,
      print: doPrint,
      addOnCurrentPage: addOnCurrentPage
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
