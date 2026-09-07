/**
 * LiftCore — صفحة تفاصيل التنبيه (عرض + طباعة)
 */
(function (global) {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function alertId() {
    return (document.body && document.body.getAttribute('data-alert-id')) || '';
  }

  function setLoading(msg) {
    var html = '<tr><td colspan="20" style="text-align:center;padding:24px;color:#888">' + esc(msg) + '</td></tr>';
    var pb = document.getElementById('print-body');
    var sb = document.getElementById('screen-body');
    if (pb) pb.innerHTML = html;
    if (sb) sb.innerHTML = html.replace(/#888/g, 'var(--text3)');
  }

  function buildRowHtml(columns, row) {
    var cells = Array.isArray(row) ? row.slice() : (row.cells || []).slice();
    var wa = row && row.wa;
    if (wa && global.LiftCoreFinancialWa) {
      cells.push(global.LiftCoreFinancialWa.buttonHtml(wa.type, wa.id));
    } else if (columns[columns.length - 1] === 'واتساب') {
      cells.push('—');
    }
    return cells.map(function (cell, i) {
      var cls = i === 1 ? ' class="td-name"' : '';
      var sty = i === 0 ? ' class="td-code"' : '';
      var attr = i === 1 ? ' class="td-name"' : sty;
      var html = (typeof cell === 'string' && cell.indexOf('<button') >= 0) ? cell : esc(String(cell == null ? '—' : cell));
      return '<td' + attr + '>' + html + '</td>';
    }).join('');
  }

  function renderTable(columns, rows, headId, bodyId, isPrint) {
    var head = document.getElementById(headId);
    var body = document.getElementById(bodyId);
    if (!head || !body) return;
    head.innerHTML = columns.map(function (c) { return '<th>' + esc(c) + '</th>'; }).join('');
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="' + columns.length + '" style="text-align:center;padding:24px;color:' +
        (isPrint ? '#888' : 'var(--text3)') + '">لا توجد بيانات</td></tr>';
      return;
    }
    body.innerHTML = rows.map(function (row) {
      return '<tr>' + buildRowHtml(columns, row) + '</tr>';
    }).join('');
  }

  async function load() {
    var id = alertId();
    if (!id) {
      setLoading('معرّف التنبيه غير موجود');
      return;
    }
    setLoading('جاري تحميل البيانات...');
    try {
      var res = await fetch('/api/dashboard/drill/' + encodeURIComponent(id), { credentials: 'same-origin' });
      var data = await res.json();
      if (!res.ok) throw new Error(data.error || 'خطأ في التحميل');

      var title = data.title || 'تفاصيل التنبيه';
      var count = data.count != null ? data.count : (data.rows || []).length;
      var countTxt = '(' + count + ' سجل)';
      document.title = 'LiftCore — ' + title;

      document.getElementById('screen-title').textContent = title;
      document.getElementById('screen-count').textContent = countTxt;
      document.getElementById('print-title').textContent = title;
      document.getElementById('footer-label').textContent = title;
      var info = document.getElementById('table-info');
      if (info) info.textContent = 'عرض ' + count + ' سجل';

      var back = document.getElementById('alert-back-link');
      if (back && data.link) back.href = data.link;

      var src = document.getElementById('alert-source-link');
      if (src && data.link) {
        src.href = data.link;
        src.style.display = 'inline-flex';
      }

      if (global.LiftCoreFormat && global.LiftCoreFormat.setReportDateEl) {
        global.LiftCoreFormat.setReportDateEl('rpt-date-range');
        global.LiftCoreFormat.setReportDateEl('footer-date');
      }

      renderTable(data.columns, data.rows || [], 'print-head', 'print-body', true);
      renderTable(data.columns, data.rows || [], 'screen-head', 'screen-body', false);
    } catch (e) {
      setLoading('تعذّر تحميل البيانات');
      var st = document.getElementById('screen-title');
      if (st) st.textContent = 'خطأ في التحميل';
    }
  }

  global.openSidebar = function () {
    document.getElementById('sidebar').classList.add('open');
    var ov = document.getElementById('overlay');
    if (ov) ov.classList.add('open');
  };
  global.closeSidebar = function () {
    document.getElementById('sidebar').classList.remove('open');
    var ov = document.getElementById('overlay');
    if (ov) ov.classList.remove('open');
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})(window);
