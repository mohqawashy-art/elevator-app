/* LiftCore — كارت عرض المصعد + بيان المصروفات */
(function (global) {
  'use strict';

  var TYPE_CLASS = {
    'قطع غيار': 'cp-type-parts',
    'صرف مخزن': 'cp-type-maint',
    'شراء': 'cp-type-inv',
    'استخدام في صيانة': 'cp-type-maint',
  };

  function L(s) {
    return global.LiftCoreDisplay ? global.LiftCoreDisplay.text(s) : s;
  }

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function fmt(n) {
    if (global.LiftCoreDisplay) return global.LiftCoreDisplay.fmtMoney(n);
    return (n || 0).toLocaleString('en-US', { maximumFractionDigits: 2 }) + ' \u20C1';
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    if (global.fmtDateDMY) return global.fmtDateDMY(iso);
    return iso.slice(0, 10);
  }

  function fetchProfile(elevatorId) {
    return fetch('/api/elevators/' + elevatorId + '/profile').then(function (r) {
      if (!r.ok) throw new Error('profile fetch failed');
      return r.json();
    });
  }

  function renderCostsBlock(data) {
    var c = data.costs || {};
    var html = '<div class="cp-financial">';
    html += '<div class="cp-fin-title">' + L('مصروفات المصعد (تكلفة الشركة)')
      + '<span class="cp-fin-period">' + L('قطع غيار + صرف مخزن') + '</span></div>';
    html += '<div class="cp-fin-total"><span>' + L('إجمالي ما صُرف على المصعد') + '</span><span>' + fmt(c.total) + '</span></div>';
    html += '<div class="cp-fin-row"><span>' + L('تكلفة قطع الغيار (شراء)') + '</span><span>' + fmt(c.parts_total) + '</span></div>';
    html += '<div class="cp-fin-row"><span>' + L('صرف من المخزن') + '</span><span>' + fmt(c.stock_total) + '</span></div>';
    html += '<div class="cp-fin-row"><span>' + L('عدد الحركات') + '</span><span style="font-family:var(--font-en)">' + (c.count || 0) + '</span></div>';
    html += '</div>';

    var rows = c.ledger || [];
    html += '<div class="cp-section">' + L('بيان المصروفات — كل ما صُرف على هذا المصعد') + '</div>';
    if (!rows.length) {
      html += '<div class="cp-empty">' + L('لا توجد مصروفات مسجّلة لهذا المصعد بعد') + '</div>';
      return html;
    }

    html += '<table class="cp-table"><thead><tr>'
      + '<th>' + L('التاريخ') + '</th>'
      + '<th>' + L('الكود') + '</th>'
      + '<th>' + L('النوع') + '</th>'
      + '<th>' + L('البيان') + '</th>'
      + '<th>' + L('التفاصيل') + '</th>'
      + '<th>' + L('المبلغ') + '</th>'
      + '</tr></thead><tbody>';
    rows.forEach(function (row) {
      var cls = TYPE_CLASS[row.type] || 'cp-type-maint';
      html += '<tr>'
        + '<td class="cp-date">' + esc(fmtDate(row.date)) + '</td>'
        + '<td style="font-family:var(--font-en)">' + esc(row.code) + '</td>'
        + '<td><span class="cp-type ' + cls + '">' + esc(L(row.type)) + '</span></td>'
        + '<td>' + esc(L(row.description || '—')) + '</td>'
        + '<td>' + esc(L(row.detail || '—')) + '</td>'
        + '<td class="cp-amount">' + (row.amount > 0 ? fmt(row.amount) : '—') + '</td>'
        + '</tr>';
    });
    html += '</tbody></table>';
    return html;
  }

  function renderActivityBlock(data) {
    var a = data.activity || {};
    var html = '<div class="cp-section">' + L('نشاط المصعد') + '</div>';
    html += '<div class="ep-activity-stats">';
    html += '<div class="ep-act-stat"><span class="ep-act-val" style="font-family:var(--font-en)">' + (a.visits_count || 0) + '</span><span class="ep-act-label">' + L('زيارة صيانة') + '</span></div>';
    html += '<div class="ep-act-stat"><span class="ep-act-val" style="font-family:var(--font-en)">' + (a.faults_count || 0) + '</span><span class="ep-act-label">' + L('عطل') + '</span></div>';
    html += '</div>';

    if (a.recent_visits && a.recent_visits.length) {
      html += '<div class="ep-sub-title">' + L('آخر الزيارات') + '</div><table class="cp-table"><thead><tr>'
        + '<th>' + L('التاريخ') + '</th><th>' + L('الكود') + '</th><th>' + L('النوع') + '</th><th>' + L('الحالة') + '</th>'
        + '</tr></thead><tbody>';
      a.recent_visits.forEach(function (v) {
        html += '<tr><td class="cp-date">' + esc(fmtDate(v.date)) + '</td>'
          + '<td style="font-family:var(--font-en)">' + esc(v.code) + '</td>'
          + '<td>' + esc(L(v.type)) + '</td><td>' + esc(L(v.status)) + '</td></tr>';
      });
      html += '</tbody></table>';
    }
    if (a.recent_faults && a.recent_faults.length) {
      html += '<div class="ep-sub-title">' + L('آخر الأعطال') + '</div><table class="cp-table"><thead><tr>'
        + '<th>' + L('التاريخ') + '</th><th>' + L('الكود') + '</th><th>' + L('النوع') + '</th><th>' + L('الحالة') + '</th>'
        + '</tr></thead><tbody>';
      a.recent_faults.forEach(function (f) {
        html += '<tr><td class="cp-date">' + esc(fmtDate(f.date)) + '</td>'
          + '<td style="font-family:var(--font-en)">' + esc(f.code) + '</td>'
          + '<td>' + esc(L(f.type)) + '</td><td>' + esc(L(f.status)) + '</td></tr>';
      });
      html += '</tbody></table>';
    }
    return html;
  }

  function renderPanel(data) {
    return renderCostsBlock(data) + renderActivityBlock(data);
  }

  function loadIntoElement(el, elevatorId) {
    if (!el || !elevatorId) return Promise.resolve();
    el.innerHTML = '<div class="cp-loading">' + L('جاري تحميل بيان المصروفات...') + '</div>';
    return fetchProfile(elevatorId).then(function (data) {
      el.innerHTML = renderPanel(data);
      if (global.LiftCoreI18n && global.LiftCoreDisplay && global.LiftCoreDisplay.isEn()) {
        global.LiftCoreI18n.apply('en');
      }
      return data;
    }).catch(function () {
      el.innerHTML = '<div class="cp-empty">' + L('تعذر تحميل بيان المصروفات') + '</div>';
    });
  }

  global.LiftCoreElevProfile = {
    fetch: fetchProfile,
    render: renderPanel,
    loadIntoElement: loadIntoElement,
  };
})(typeof window !== 'undefined' ? window : this);
