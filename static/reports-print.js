/**
 * LiftCore — تحضير الطباعة وتصدير PDF للتقارير
 */
(function (global) {
  'use strict';

  function todayLabel() {
    try {
      return new Date().toLocaleDateString('ar-SA', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
    } catch (e) {
      return new Date().toLocaleDateString('en-GB');
    }
  }

  function setFooterDates() {
    var label = todayLabel();
    ['footer-date', 'r-print-date'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = label;
    });
    var range = document.getElementById('rpt-date-range');
    if (range && range.textContent.indexOf('تاريخ التقرير') >= 0) {
      range.textContent = 'تاريخ التقرير: ' + label;
    }
  }

  function syncPrintStats() {
    var stats = document.querySelectorAll('.content > .rpt-stat-row .rpt-stat-val, .rpt-stat-row:not(.screen-only) .rpt-stat-val');
    if (!stats.length) {
      stats = document.querySelectorAll('.rpt-stat-val');
    }
    var grid = document.getElementById('rpt-print-stats') ||
      document.querySelector('.rpt-page .rpt-print-stats') ||
      document.querySelector('.rpt-page [style*="grid-template-columns"]');
    if (!grid || !stats.length) return;
    var nums = grid.querySelectorAll('.rpt-print-stat-val, div[style*="font-size:18px"], div[style*="font-size: 18px"]');
    stats.forEach(function (el, i) {
      if (nums[i]) nums[i].innerHTML = el.innerHTML;
    });
  }

  function resizeDashboardCharts() {
    if (!global.__lcDashboardCharts || !global.Chart) return;
    global.__lcDashboardCharts.forEach(function (chart) {
      try {
        chart.resize();
      } catch (e) { /* ignore */ }
    });
  }

  function ensureDashboardPrintTitle() {
    if (!document.body || document.body.getAttribute('data-report-dashboard') !== '1') return;
    var sub = document.getElementById('report-subtitle');
    if (!sub) return;
    var el = document.getElementById('rpt-print-title');
    if (!el) {
      el = document.createElement('div');
      el.id = 'rpt-print-title';
      var content = document.querySelector('.content');
      if (content) content.insertBefore(el, content.firstChild);
    }
    el.textContent = sub.textContent || '';
  }

  function prepare() {
    setFooterDates();
    syncPrintStats();
    ensureDashboardPrintTitle();
    if (typeof global.__lcSyncPrintFromScreen === 'function') {
      global.__lcSyncPrintFromScreen();
    }
    resizeDashboardCharts();
    document.documentElement.classList.add('lc-printing');
  }

  function cleanup() {
    document.documentElement.classList.remove('lc-printing');
  }

  function report() {
    prepare();
    global.setTimeout(function () {
      global.print();
    }, 120);
  }

  function pdf() {
    report();
  }

  global.LiftCorePrint = {
    prepare: prepare,
    report: report,
    pdf: pdf,
  };

  global.printReport = report;
  global.exportPDF = pdf;

  global.addEventListener('beforeprint', prepare);
  global.addEventListener('afterprint', cleanup);
})(window);
