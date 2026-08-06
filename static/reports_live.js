/**
 * LiftCore — ربط التقارير بالبيانات الحقيقية (شاشة + طباعة + فلاتر + تصدير)
 */
(function (global) {
  'use strict';

var __lcReportDomPager = null;
  var __lcDashboardCharts = [];
  var __lcReportData = [];
  var __lcReportId = null;
  var __lcDashboardCache = null;
  var __lcReportLoaded = false;

  var REPORT_API = {
    'report-clients': '/api/reports/clients',
    'report-elevators': '/api/reports/elevators',
    'report-contracts': '/api/reports/contracts',
    'report-technicians': '/api/reports/technicians',
    'report-maintenance': '/api/reports/visits',
    'report-faults': '/api/reports/faults',
    'report-revenues': '/api/reports/revenues',
    'report-expenses': '/api/reports/expenses',
    'report-invoices': '/api/reports/invoices',
    'report-parts': '/api/reports/parts-billing',
    'report-inventory': '/api/reports/inventory',
    'report-stock': '/api/reports/stock',
  };

  var REPORT_DATE_FIELD = {
    'report-maintenance': 'visit_date',
    'report-faults': 'reported_date',
    'report-revenues': 'date',
    'report-expenses': 'date',
    'report-invoices': 'date',
    'report-parts': 'date',
    'report-stock': 'date',
  };

  var MONTHS_AR = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function fmtNum(v) {
    if (typeof v === 'number' && !isNaN(v)) {
      return v.toLocaleString('en-US');
    }
    return esc(v);
  }

  function joinClientContract(row) {
    var c = row.customer || '—';
    var ct = row.contract || '—';
    return c + ' / ' + ct;
  }

  function reportRowCells(reportId, row) {
    switch (reportId) {
      case 'report-clients':
        return [row.code, row.name, row.city, row.district, row.phone, row.elevators, row.contract_status, row.status];
      case 'report-elevators':
        return [row.code, row.customer, row.building, row.city, row.elev_type, row.brand, row.capacity, row.status, row.next_maint];
      case 'report-contracts':
        return [row.code, row.customer, row.contract_type, row.start_date, row.end_date, row.elevators, row.value, row.total, row.status, row.inv_status];
      case 'report-technicians':
        return [row.code, row.name, row.phone, row.job_title, row.specialization, row.city, row.status, row.emergency, row.visits];
      case 'report-maintenance':
        return [row.code, row.customer, row.elevator, row.technician, row.visit_type, row.visit_date, row.visit_time || '—', row.priority, row.status];
      case 'report-faults':
        return [row.code, row.customer, row.elevator, row.fault_type, row.priority, row.technician, row.response, row.status, row.billed];
      case 'report-revenues':
        return [row.code, joinClientContract(row), row.date, row.revenue_type, row.pay_method, row.total, row.status, row.created_by || '—'];
      case 'report-expenses':
        return [row.code, row.date, row.expense_type, row.description, row.responsible, row.pay_method, row.amount, row.created_by || '—'];
      case 'report-invoices':
        return [row.code, row.invoice_type, joinClientContract(row), row.date, row.description, row.total, row.pay_method, row.status];
      case 'report-parts':
        return [
          row.code, row.customer, row.contract, row.elevator, row.technician,
          row.date, row.description, row.sell_price, row.paid_amount, row.profit, row.pay_method, row.status,
        ];
      case 'report-inventory':
        return [row.code, row.name, row.category, row.current_qty, row.min_qty, row.buy_price, row.stock_value, row.supplier, row.order_status];
      case 'report-stock':
        return [row.code, row.date, row.direction, row.movement_type, row.item, row.quantity, row.unit_price, row.total_value, row.technician, row.reason];
      default:
        return Object.values(row);
    }
  }

  var BADGE_COLS = {
    'report-clients': [6, 7],
    'report-elevators': [7],
    'report-contracts': [8, 9],
    'report-technicians': [6, 7],
    'report-maintenance': [7, 8],
    'report-faults': [4, 7, 8],
    'report-revenues': [6],
    'report-invoices': [7],
    'report-parts': [11],
    'report-inventory': [8],
    'report-stock': [2, 3],
  };

  function badgeClassFor(val) {
    var s = String(val || '');
    if (/نشط|محصّل|مكتمل|مدفوع|تم الاصلاح|مغلق|وارد|نعم|مدفوعة/i.test(s)) return 'rpt-badge-ok';
    if (/متأخر|متوقف|منتهي|خارج|مفتوح|غير مدفوع|نافد|صادر|غير مفوتر/i.test(s)) return 'rpt-badge-danger';
    if (/جزئ|معلق|قيد|عاجل|تحت الصيانة|منخفض|أحياناً|متأخرة/i.test(s)) return 'rpt-badge-warn';
    if (/مجدولة|معلقة|بدون|غير نشط/i.test(s)) return 'rpt-badge-muted';
    return 'rpt-badge-info';
  }

  function screenBadgeClass(val) {
    var cls = badgeClassFor(val);
    if (cls === 'rpt-badge-ok') return 'badge badge-green';
    if (cls === 'rpt-badge-danger') return 'badge badge-red';
    if (cls === 'rpt-badge-warn') return 'badge badge-gold';
    if (cls === 'rpt-badge-muted') return 'badge badge-gray';
    return 'badge badge-blue';
  }

  function buildRowHtml(reportId, row, forPrint) {
    var cells = reportRowCells(reportId, row);
    var badgeCols = BADGE_COLS[reportId] || [];
    return cells.map(function (val, i) {
      if (typeof val === 'number') {
        return '<td class="num ltr">' + fmtNum(val) + '</td>';
      }
      var str = String(val == null ? '' : val);
      if (badgeCols.indexOf(i) >= 0 && str) {
        if (forPrint) {
          return '<td><span class="rpt-badge ' + badgeClassFor(str) + '">' + esc(str) + '</span></td>';
        }
        return '<td><span class="' + screenBadgeClass(str) + '">' + esc(str) + '</span></td>';
      }
      if (/^\d{4}-\d{2}-\d{2}/.test(str) || /^[A-Z]{2,}-/.test(str) || /^\+?\d{7,}$/.test(str.replace(/\s/g, ''))) {
        return '<td class="num ltr">' + esc(str) + '</td>';
      }
      return '<td>' + esc(str) + '</td>';
    }).join('');
  }

function __lcLoadPagination(cb) {
    if (global.LiftCorePagination) { cb(); return; }
  var s = document.createElement('script');
  s.src = '/static/liftcore-pagination.js?v=2';
  s.onload = cb;
  document.head.appendChild(s);
}

function hookReportPagination(reset) {
  var tbody = document.getElementById('report-tbody');
    if (!tbody || !global.LiftCorePagination) return;

  var footer = tbody.closest('.table-wrap');
  footer = footer ? footer.querySelector('.table-footer') : document.querySelector('.table-footer');
  if (!footer) return;

  var container = footer.querySelector('#page-btns');
  if (!container) {
    container = document.createElement('div');
    container.className = 'pagination';
    container.id = 'page-btns';
    footer.appendChild(container);
  }

  if (!__lcReportDomPager) {
      __lcReportDomPager = global.LiftCorePagination.createDom({
      tbody: tbody,
      container: container,
      infoEl: footer.querySelector('#table-info'),
      pageSize: 10,
    });

      var origFilter = global.filterTable;
      global.filterTable = function () {
      if (typeof origFilter === 'function') origFilter();
      Array.prototype.forEach.call(tbody.querySelectorAll('tr'), function (tr) {
        if (tr.querySelector('td[colspan]')) return;
        tr.dataset.lcSearchHidden = tr.style.display === 'none' ? '1' : '0';
      });
      __lcReportDomPager.apply(true);
    };
  }

  Array.prototype.forEach.call(tbody.querySelectorAll('tr'), function (tr) {
    if (tr.querySelector('td[colspan]')) return;
    if (tr.dataset.lcSearchHidden == null) tr.dataset.lcSearchHidden = '0';
  });
  __lcReportDomPager.apply(reset !== false);
}

  function syncPrintTable(reportId, data) {
    var printBody = document.querySelector('.rpt-page .rpt-table tbody, #print-tbody');
    if (!printBody || !data) return;
    if (!data.length) {
      printBody.innerHTML = '<tr><td colspan="20" style="text-align:center;padding:16px;color:#888">لا توجد بيانات</td></tr>';
      return;
    }
    printBody.innerHTML = data.map(function (row) {
      return '<tr>' + buildRowHtml(reportId, row, true) + '</tr>';
    }).join('');
  }

  function setStatValues(values) {
    if (!values || !values.length) return;
    document.querySelectorAll('.content > .rpt-stat-row .rpt-stat-val').forEach(function (el, i) {
      if (values[i] != null) el.innerHTML = values[i];
    });
    var grid = document.getElementById('rpt-print-stats') ||
      document.querySelector('.rpt-page .rpt-print-stats') ||
      document.querySelector('.rpt-page [style*="grid-template-columns"]');
    if (grid) {
      var nums = grid.querySelectorAll('.rpt-print-stat-val, div[style*="font-size:18px"], div[style*="font-size: 18px"]');
      nums.forEach(function (el, i) {
        if (values[i] != null) el.innerHTML = values[i];
      });
    }
  }

  function __lcSyncPrintFromScreen() {
    if (!__lcReportId || !__lcReportData.length) return;
    var filtered = __lcReportData.filter(function (row) {
      return rowPassesFilters(__lcReportId, row);
    });
    syncPrintTable(__lcReportId, filtered);
    updateReportStats(__lcReportId, filtered);
  }

  global.__lcSyncPrintFromScreen = __lcSyncPrintFromScreen;

  function computeReportStats(reportId, data) {
    var today = new Date();
    var month = today.getMonth() + 1;
    var year = today.getFullYear();

    function sumField(field) {
      return data.reduce(function (s, r) { return s + (parseFloat(r[field]) || 0); }, 0);
    }

    switch (reportId) {
      case 'report-clients':
        return [
          fmtNum(data.length),
          fmtNum(data.filter(function (r) { return r.status === 'نشط'; }).length),
          fmtNum(data.filter(function (r) { return r.contract_status === 'بدون عقد'; }).length),
          fmtNum(data.reduce(function (s, r) { return s + (r.elevators || 0); }, 0)),
        ];
      case 'report-elevators':
        return [
          fmtNum(data.length),
          fmtNum(data.filter(function (r) { return r.status === 'نشط'; }).length),
          fmtNum(data.filter(function (r) { return r.status === 'تحت الصيانة'; }).length),
          fmtNum(data.filter(function (r) { return r.status === 'متوقف' || r.status === 'خارج الخدمة'; }).length),
        ];
      case 'report-contracts': {
        var active = data.filter(function (r) { return r.status === 'نشط'; }).length;
        var expiring = data.filter(function (r) {
          if (!r.end_date) return false;
          var d = new Date(r.end_date);
          var diff = (d - today) / 86400000;
          return diff >= 0 && diff <= 30;
        }).length;
        return [
          fmtNum(data.length),
          fmtNum(active),
          fmtNum(expiring),
          fmtNum(sumField('total')) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>',
        ];
      }
      case 'report-technicians': {
        var activeTech = data.filter(function (r) {
          return r.status === 'نشط' || r.status === 'متاح' || r.status === 'مشغول';
        }).length;
        var visitsMonth = data.reduce(function (s, r) { return s + (r.visits || 0); }, 0);
        var avg = activeTech ? (visitsMonth / activeTech).toFixed(1) : '0';
        return [fmtNum(data.length), fmtNum(activeTech), fmtNum(visitsMonth), avg];
      }
      case 'report-maintenance':
        return [
          fmtNum(data.length),
          fmtNum(data.filter(function (r) { return r.status === 'مكتملة'; }).length),
          fmtNum(data.filter(function (r) { return r.status === 'مجدولة'; }).length),
          fmtNum(data.filter(function (r) { return r.status === 'متأخرة'; }).length),
        ];
      case 'report-faults':
        return [
          fmtNum(data.length),
          fmtNum(data.filter(function (r) { return r.status === 'مفتوح'; }).length),
          fmtNum(data.filter(function (r) { return r.status === 'قيد المعالجة'; }).length),
          fmtNum(data.filter(function (r) {
            return r.status === 'تم الاصلاح' || r.status === 'مغلق';
          }).length),
        ];
      case 'report-revenues': {
        var totalRev = sumField('total');
        var collected = data.filter(function (r) { return r.status === 'محصّل'; }).reduce(function (s, r) { return s + (r.total || 0); }, 0);
        var pending = data.filter(function (r) { return r.status === 'معلق'; }).reduce(function (s, r) { return s + (r.total || 0); }, 0);
        return [
          fmtNum(totalRev) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>',
          fmtNum(collected) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>',
          fmtNum(pending) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>',
          fmtNum(data.length),
        ];
      }
      case 'report-expenses': {
        var totalExp = sumField('amount');
        var salaries = data.filter(function (e) { return e.expense_type === 'رواتب'; }).reduce(function (s, e) { return s + (e.amount || 0); }, 0);
        var partsExp = data.filter(function (e) { return e.expense_type === 'قطع غيار'; }).reduce(function (s, e) { return s + (e.amount || 0); }, 0);
        var other = totalExp - salaries - partsExp;
        return [
          fmtNum(totalExp) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>',
          fmtNum(salaries) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>',
          fmtNum(partsExp) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>',
          fmtNum(other) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>',
        ];
      }
      case 'report-invoices': {
        var invTotal = sumField('total');
        var paid = data.filter(function (r) {
          return r.status === 'مدفوعة' || r.status === 'مدفوع' || r.status === 'محصّل';
        }).length;
        var unpaid = data.filter(function (r) {
          return r.status === 'غير مدفوعة' || r.status === 'غير مدفوع' || r.status === 'متأخر';
        }).length;
        return [
          fmtNum(data.length),
          fmtNum(paid),
          fmtNum(unpaid),
          fmtNum(invTotal) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>',
        ];
      }
      case 'report-parts': {
        var sellTotal = sumField('sell_price');
        var profitTotal = sumField('profit');
        var collected = data.filter(function (r) {
          return r.status === 'محصّل' || r.status === 'مدفوع';
        }).length;
        var uncollected = data.filter(function (r) {
          return r.status === 'غير محصل' || r.status === 'غير مدفوع';
        }).length;
        return [
          fmtNum(data.length),
          fmtNum(sellTotal) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>',
          fmtNum(profitTotal) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>',
          fmtNum(collected) + ' / ' + fmtNum(uncollected),
        ];
      }
      case 'report-inventory': {
        var totalVal = sumField('stock_value');
        var lowItems = data.filter(function (i) { return i.order_status === 'منخفض'; }).length;
        var outItems = data.filter(function (i) { return i.order_status === 'نافد'; }).length;
        return [fmtNum(data.length), fmtNum(totalVal) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>', fmtNum(lowItems), fmtNum(outItems)];
      }
      case 'report-stock': {
        var inward = data.filter(function (r) { return r.direction === 'وارد'; }).length;
        var outward = data.filter(function (r) { return r.direction === 'صادر'; }).length;
        var outVal = data.filter(function (r) { return r.direction === 'صادر'; }).reduce(function (s, r) { return s + (r.total_value || 0); }, 0);
        return [fmtNum(data.length), fmtNum(inward), fmtNum(outward), fmtNum(outVal) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>'];
      }
      default:
        return [fmtNum(data.length)];
    }
  }

  function updateReportStats(reportId, data) {
    setStatValues(computeReportStats(reportId, data));
  }

  function populateFilterSelects(reportId, data) {
    var card = document.querySelector('.filter-card');
    if (!card || !data.length) return;
    var selects = card.querySelectorAll('select');
    if (!selects.length) return;

    function unique(vals) {
      var seen = {};
      return vals.filter(function (v) {
        v = String(v || '').trim();
        if (!v || seen[v]) return false;
        seen[v] = 1;
        return true;
      }).sort();
    }

    var cityIdx = -1;
    var statusIdx = -1;
    if (reportId === 'report-clients') {
      cityIdx = 0;
      if (selects[1]) selects[1].id = 'f-contract-status';
      if (selects[2]) selects[2].id = 'f-status';
    } else if (reportId === 'report-elevators') {
      cityIdx = 0;
      if (selects[1]) selects[1].id = 'f-status';
    } else if (reportId === 'report-contracts') {
      if (selects[0]) selects[0].id = 'f-status';
      if (selects[1]) selects[1].id = 'f-inv-status';
    } else if (reportId === 'report-faults' || reportId === 'report-maintenance') {
      if (selects[0]) selects[0].id = 'f-status';
    }

    if (cityIdx >= 0 && selects[cityIdx] && !selects[cityIdx].dataset.liveReady) {
      var cities = unique(data.map(function (r) { return r.city; }));
      selects[cityIdx].id = 'f-city';
      selects[cityIdx].innerHTML = '<option value="">الكل</option>' + cities.map(function (c) {
        return '<option value="' + esc(c) + '">' + esc(c) + '</option>';
      }).join('');
      selects[cityIdx].dataset.liveReady = '1';
    }

    ['f-status', 'f-contract-status', 'f-inv-status'].forEach(function (id) {
      var sel = document.getElementById(id);
      if (!sel || sel.dataset.liveReady) return;
      var field = id === 'f-contract-status' ? 'contract_status' : (id === 'f-inv-status' ? 'inv_status' : 'status');
      var vals = unique(data.map(function (r) { return r[field]; }));
      if (!vals.length) return;
      sel.innerHTML = '<option value="">الكل</option>' + vals.map(function (v) {
        return '<option value="' + esc(v) + '">' + esc(v) + '</option>';
      }).join('');
      sel.dataset.liveReady = '1';
    });

    selects.forEach(function (sel) {
      if (sel.dataset.liveHooked) return;
      sel.addEventListener('change', function () {
        if (typeof global.filterTable === 'function') global.filterTable();
      });
      sel.dataset.liveHooked = '1';
    });
  }

  function rowPassesFilters(reportId, row) {
    var searchEl = document.getElementById('f-search');
    var q = searchEl ? searchEl.value.toLowerCase().trim() : '';
    if (q) {
      var txt = reportRowCells(reportId, row).join(' ').toLowerCase();
      if (txt.indexOf(q) === -1) return false;
    }

    var citySel = document.getElementById('f-city');
    if (citySel && citySel.value && row.city !== citySel.value) return false;

    var statusSel = document.getElementById('f-status');
    if (statusSel && statusSel.value && row.status !== statusSel.value) return false;

    var contractSel = document.getElementById('f-contract-status');
    if (contractSel && contractSel.value && row.contract_status !== contractSel.value) return false;

    var invSel = document.getElementById('f-inv-status');
    if (invSel && invSel.value && row.inv_status !== invSel.value) return false;

    var dateField = REPORT_DATE_FIELD[reportId];
    if (dateField && row[dateField]) {
      var fromEl = document.getElementById('f-from');
      var toEl = document.getElementById('f-to');
      var d = row[dateField].slice(0, 10);
      if (fromEl && fromEl.value && d < fromEl.value) return false;
      if (toEl && toEl.value && d > toEl.value) return false;
    }

    return true;
  }

  function renderReportTable(reportId, data) {
    var filtered = data.filter(function (row) { return rowPassesFilters(reportId, row); });
    var tbody = document.getElementById('report-tbody');
    if (!tbody) return;

    var countEl = document.getElementById('report-count');
    if (countEl) countEl.textContent = filtered.length + ' سجل';

    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="20" style="text-align:center;padding:30px;color:var(--text3)">لا توجد بيانات</td></tr>';
      syncPrintTable(reportId, []);
      updateReportStats(reportId, filtered);
      __lcLoadPagination(function () { hookReportPagination(true); });
      return;
    }

      tbody.innerHTML = filtered.map(function (row) {
        return '<tr>' + buildRowHtml(reportId, row, false) + '</tr>';
    }).join('');

    syncPrintTable(reportId, filtered);
    updateReportStats(reportId, filtered);

    var info = document.getElementById('table-info');
    if (info) info.textContent = 'عرض ' + filtered.length + ' سجل';

    __lcLoadPagination(function () { hookReportPagination(true); });
  }

  function installLiveFilterTable(reportId) {
    global.filterTable = function () {
      if (__lcReportData.length && __lcReportId === reportId) {
        renderReportTable(reportId, __lcReportData);
      }
    };

    ['f-from', 'f-to'].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el || el.dataset.liveHooked) return;
      el.addEventListener('input', global.filterTable);
      el.dataset.liveHooked = '1';
    });
  }

  function applyUrlFilters() {
    var params = new URLSearchParams(global.location.search);
    var q = params.get('q') || params.get('search') || '';
    if (q) {
      var search = document.getElementById('f-search') || document.getElementById('search-input');
      if (search) search.value = q;
    }
    var status = params.get('status');
    if (status) {
      var sel = document.getElementById('f-status');
      if (sel) sel.value = status;
    }
    if (typeof global.filterTable === 'function') global.filterTable();
  }

  function applyReportPayload(reportId, data) {
    __lcReportData = Array.isArray(data) ? data : [];
    __lcReportId = reportId;
    __lcReportLoaded = true;
    populateFilterSelects(reportId, __lcReportData);
    installLiveFilterTable(reportId);
    renderReportTable(reportId, __lcReportData);
    var dateEl = document.getElementById('rpt-date-range');
    if (dateEl) dateEl.textContent = 'تاريخ التقرير: ' + new Date().toLocaleDateString('ar-SA');
    applyUrlFilters();
  }

  async function loadReportData(reportId, extraParams) {
    var apiUrl = REPORT_API[reportId];
    if (!apiUrl) return;
    if (__lcReportLoaded && __lcReportId === reportId) return;

    try {
      var qs = extraParams || '';
      if (!qs) {
        var params = new URLSearchParams(global.location.search);
        var year = params.get('year');
        var month = params.get('month');
        var bits = [];
        if (year) bits.push('year=' + encodeURIComponent(year));
        if (month) bits.push('month=' + encodeURIComponent(month));
        qs = bits.join('&');
      }

      var res = await fetch(apiUrl + (qs ? '?' + qs : ''), { credentials: 'same-origin' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var data = await res.json();

      applyReportPayload(reportId, data);
      __lcReportLoaded = true;
    } catch (e) {
      if (e && (e.name === 'AbortError' || (global.document && global.document.visibilityState === 'hidden'))) return;
      console.error('Report API error:', e);
      var errBody = document.getElementById('report-tbody');
      if (errBody && !__lcReportLoaded) {
        errBody.innerHTML = '<tr><td colspan="20" style="text-align:center;padding:30px;color:var(--danger)">تعذّر تحميل البيانات — حدّث الصفحة</td></tr>';
      }
    }
  }

  function setText(id, val) {
    var el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function destroyDashboardCharts() {
    __lcDashboardCharts.forEach(function (c) { try { c.destroy(); } catch (e) { /* ignore */ } });
    __lcDashboardCharts = [];
  }

  function makeDashboardChart(id, type, labels, datasets, opts) {
    var ctx = document.getElementById(id);
    if (!ctx || !global.Chart) return null;
    var chart = new global.Chart(ctx, {
      type: type,
      data: { labels: labels, datasets: datasets },
      options: Object.assign({
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: 'rgba(228,234,245,.7)', font: { family: 'IBM Plex Sans Arabic', size: 11 } } } },
        scales: (type === 'pie' || type === 'doughnut') ? {} : {
          x: { ticks: { color: 'rgba(228,234,245,.7)', font: { size: 10 } }, grid: { color: 'rgba(100,160,255,.08)' } },
          y: { ticks: { color: 'rgba(228,234,245,.7)', font: { size: 10 } }, grid: { color: 'rgba(100,160,255,.08)' } },
        },
      }, opts || {}),
    });
    __lcDashboardCharts.push(chart);
    return chart;
  }

  function badgeClass(status) {
    if (!status) return 'badge-gray';
    if (status.indexOf('نشط') >= 0 || status.indexOf('مدفوع') >= 0) return 'badge-green';
    if (status.indexOf('متأخر') >= 0 || status.indexOf('خارج') >= 0 || status.indexOf('منتهي') >= 0) return 'badge-red';
    if (status.indexOf('جزئ') >= 0 || status.indexOf('متوقف') >= 0) return 'badge-gold';
    return 'badge-blue';
  }

  function renderProgressRows(containerId, rows, valueKey, suffix, maxVal) {
    var el = document.getElementById(containerId);
    if (!el || !rows || !rows.length) {
      if (el) el.innerHTML = '<div style="color:var(--text3);font-size:12px;padding:8px">لا توجد بيانات</div>';
      return;
    }
    if (!maxVal) {
      maxVal = Math.max.apply(null, rows.map(function (r) { return r[valueKey] || 0; })) || 1;
    }
    var colors = ['var(--accent)', 'var(--success)', 'var(--gold)', 'var(--warning)', '#7c6fff'];
    el.innerHTML = rows.map(function (r, i) {
      var val = r[valueKey] || 0;
      var pct = Math.round(val / maxVal * 100);
      return '<div class="prog-row"><span class="prog-label">' + esc(r.name) + '</span>' +
        '<div class="prog-bar"><div class="prog-fill" style="width:' + pct + '%;--pf-color:' + colors[i % colors.length] + '"></div></div>' +
        '<span class="prog-val">' + fmtNum(val) + (suffix || '') + '</span></div>';
    }).join('');
  }

  function fillDashboardTables(d) {
    var topBody = document.querySelector('#dash-top-clients tbody');
    if (topBody) {
      var clients = d.top_clients || [];
      topBody.innerHTML = clients.length ? clients.map(function (c, i) {
        return '<tr><td class="td-num">' + (i + 1) + '</td><td class="td-name">' + esc(c.name) + '</td><td>' + esc(c.city) + '</td>' +
          '<td class="td-num">' + fmtNum(c.elevators) + '</td><td class="td-num">' + fmtNum(c.contracts) + '</td>' +
          '<td class="td-num" style="color:var(--success)">' + fmtNum(c.revenue) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span></td>' +
          '<td><span class="badge ' + badgeClass(c.status) + '">' + esc(c.status) + '</span></td></tr>';
      }).join('') : '<tr><td colspan="7" style="text-align:center;padding:16px;color:var(--text3)">لا توجد بيانات</td></tr>';
    }

    var expBody = document.querySelector('#dash-expiring tbody');
    if (expBody) {
      var exp = d.expiring_contracts_list || [];
      expBody.innerHTML = exp.length ? exp.map(function (c) {
        var badge = c.days_left <= 30 ? 'badge-red' : 'badge-gold';
        return '<tr><td class="td-code">' + esc(c.code) + '</td><td class="td-name">' + esc(c.customer) + '</td>' +
          '<td class="td-num">' + esc(c.end_date) + '</td><td><span class="badge ' + badge + '">' + fmtNum(c.days_left) + ' يوم</span></td>' +
          '<td class="td-num">' + fmtNum(c.value) + ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span></td>' +
          '<td><span class="badge ' + badgeClass(c.inv_status) + '">' + esc(c.inv_status) + '</span></td></tr>';
      }).join('') : '<tr><td colspan="6" style="text-align:center;padding:16px;color:var(--text3)">لا عقود تنتهي قريباً</td></tr>';
    }

    var downBody = document.querySelector('#dash-down-elevators tbody');
    if (downBody) {
      var downs = d.down_elevators || [];
      downBody.innerHTML = downs.length ? downs.map(function (e) {
        return '<tr><td class="td-code">' + esc(e.code) + '</td><td class="td-name">' + esc(e.customer) + '</td><td>' + esc(e.elev_type) + '</td>' +
          '<td><span class="badge ' + badgeClass(e.status) + '">' + esc(e.status) + '</span></td>' +
          '<td class="td-num">' + esc(e.last_maint) + '</td><td>' + esc(e.technician) + '</td></tr>';
      }).join('') : '<tr><td colspan="6" style="text-align:center;padding:16px;color:var(--text3)">لا مصاعد متوقفة</td></tr>';
    }

    renderProgressRows('tech-visits-prog', (d.tech_visits || []).map(function (t) {
      return { name: t.name, count: t.count };
    }), 'count', ' زيارة');

    renderProgressRows('tech-faults-prog', (d.tech_fault_rates || []).map(function (t) {
      return { name: t.name, rate: t.rate };
    }), 'rate', '%');
  }

  async function loadDashboardReport(year) {
    var sel = document.getElementById('sel-year');
    if (!year && sel) year = sel.value;
    if (!year) year = new Date().getFullYear();

    try {
      var res = await fetch('/api/dashboard?year=' + encodeURIComponent(year));
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var d = await res.json();
      __lcDashboardCache = d;

      setText('kpi-clients', d.customers);
      setText('kpi-elevators', d.elevators);
      setText('kpi-contracts', d.contracts);
      setText('kpi-revenue', fmtNum(Math.round((d.revenue || 0) / 1000)) + 'K');
      setText('kpi-faults', d.faults_open);
      setText('kpi-visits', d.visits_done);
      setText('kpi-technicians', d.technicians);
      setText('kpi-profit', fmtNum(Math.round((d.parts_profit || 0) / 1000)) + 'K');

      var subtitle = document.getElementById('report-subtitle');
      if (subtitle) subtitle.textContent = 'تقرير سنوي شامل — ' + year;

      var net = (d.revenue || 0) - (d.expenses || 0);
      var sar = ' <span class="lc-sar" role="img" aria-label="ريال سعودي"></span>';

      function fillFinRows(cardIndex, typeMap, totalId) {
        var card = document.querySelectorAll('.fin-card')[cardIndex];
        if (!card) return;
        var rows = card.querySelectorAll('.fin-row');
        var entries = Object.entries(typeMap || {});
        for (var i = 0; i < 4; i++) {
          if (!rows[i]) continue;
          var label = rows[i].querySelector('span:first-child');
          var val = rows[i].querySelector('span:last-child');
          if (entries[i]) {
            if (label) label.textContent = entries[i][0];
            if (val) val.innerHTML = fmtNum(entries[i][1]) + sar;
          } else if (val) {
            val.textContent = '—';
          }
        }
        if (totalId) {
          var totalEl = document.getElementById(totalId);
          if (totalEl) totalEl.innerHTML = fmtNum(cardIndex === 0 ? d.revenue : d.expenses) + sar;
        }
      }

      fillFinRows(0, d.revenue_by_type, 'fin-rev-total');
      fillFinRows(1, d.expense_by_type, 'fin-exp-total');

      setText('fin-net-rev', fmtNum(d.revenue));
      setText('fin-net-exp', fmtNum(d.expenses));
      var profitEl = document.getElementById('fin-net-profit');
      if (profitEl) profitEl.innerHTML = fmtNum(net) + sar;
      var marginEl = document.getElementById('fin-net-margin');
      if (marginEl) marginEl.textContent = (d.revenue ? Math.round(net / d.revenue * 1000) / 10 : 0) + '%';
      var overdueEl = document.getElementById('fin-net-overdue');
      if (overdueEl) overdueEl.innerHTML = fmtNum(d.unpaid_invoices) + sar;

      destroyDashboardCharts();
      var rev = d.monthly_revenue || [];
      var exp = d.monthly_expenses || [];
      var visits = d.monthly_visits || [];
      var faults = d.monthly_faults || [];

      makeDashboardChart('chart-revenue', 'bar', MONTHS_AR, [{
        label: 'الإيرادات',
        data: rev,
        backgroundColor: 'rgba(31,184,122,.5)',
        borderColor: 'rgba(31,184,122,.9)',
        borderWidth: 1,
        borderRadius: 4,
      }]);

      var revType = d.revenue_by_type || {};
      makeDashboardChart('chart-rev-type', 'doughnut',
        Object.keys(revType),
        [{ data: Object.values(revType), backgroundColor: ['rgba(31,184,122,.8)', 'rgba(42,159,255,.8)', 'rgba(224,144,48,.8)', 'rgba(224,72,72,.8)', 'rgba(138,155,184,.6)'], borderWidth: 0 }]);

      var elev = d.elev_status || {};
      makeDashboardChart('chart-elevators', 'doughnut',
        Object.keys(elev),
        [{ data: Object.values(elev), backgroundColor: ['rgba(31,184,122,.8)', 'rgba(42,159,255,.8)', 'rgba(224,144,48,.8)', 'rgba(224,72,72,.8)'], borderWidth: 0 }]);

      var cst = d.contract_status || {};
      makeDashboardChart('chart-contracts', 'doughnut',
        Object.keys(cst),
        [{ data: Object.values(cst), backgroundColor: ['rgba(31,184,122,.8)', 'rgba(224,144,48,.8)', 'rgba(224,72,72,.8)', 'rgba(138,155,184,.6)'], borderWidth: 0 }]);

      makeDashboardChart('chart-visits', 'bar', MONTHS_AR, [{
        label: 'الزيارات',
        data: visits,
        backgroundColor: 'rgba(42,159,255,.5)',
        borderColor: 'rgba(42,159,255,.9)',
        borderWidth: 1,
        borderRadius: 4,
      }]);

      makeDashboardChart('chart-faults', 'line', MONTHS_AR, [{
        label: 'الأعطال',
        data: faults,
        borderColor: 'rgba(224,72,72,.9)',
        backgroundColor: 'rgba(224,72,72,.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 2,
      }]);

      var expType = d.expense_by_type || {};
      makeDashboardChart('chart-expenses', 'pie',
        Object.keys(expType),
        [{ data: Object.values(expType), backgroundColor: ['rgba(224,72,72,.8)', 'rgba(224,144,48,.8)', 'rgba(42,159,255,.8)', 'rgba(138,155,184,.6)'], borderWidth: 0 }]);

      makeDashboardChart('chart-compare', 'line', MONTHS_AR, [
        { label: 'الإيرادات', data: rev, borderColor: 'rgba(31,184,122,.9)', backgroundColor: 'rgba(31,184,122,.1)', fill: true, tension: 0.4, pointRadius: 2 },
        { label: 'المصروفات', data: exp, borderColor: 'rgba(224,72,72,.9)', backgroundColor: 'rgba(224,72,72,.1)', fill: true, tension: 0.4, pointRadius: 2 },
      ]);

      fillDashboardTables(d);
    } catch (e) {
      console.error('Dashboard report error:', e);
    }
  }

  function initAnnualReportSelectors() {
    var clientSel = document.getElementById('sel-client');
    var yearSel = document.getElementById('sel-year');
    var contractSel = document.getElementById('sel-contract');
    if (yearSel && !yearSel.dataset.liveReady) {
      var cur = new Date().getFullYear();
      yearSel.innerHTML = '';
      for (var y = cur; y >= cur - 6; y--) {
        yearSel.innerHTML += '<option value="' + y + '"' + (y === cur ? ' selected' : '') + '>' + y + '</option>';
      }
      yearSel.dataset.liveReady = '1';
    }
    if (contractSel && !contractSel.dataset.liveReady) {
      contractSel.innerHTML = '<option value="">اختر العقد أولاً</option>';
      contractSel.dataset.liveReady = '1';
    }
    if (!clientSel || clientSel.dataset.liveReady) return;
    var list = global.__LC_ANNUAL_CUSTOMERS || [];
    if (!list.length) return;
    clientSel.innerHTML = '<option value="">اختر العميل</option>' +
      list.map(function (c) {
        return '<option value="' + c.id + '">' + esc(c.name) + ' (' + esc(c.code) + ')</option>';
      }).join('');
    clientSel.dataset.liveReady = '1';

    var params = new URLSearchParams(global.location.search);
    var pre = params.get('customer_id') || params.get('customer');
    var preContract = params.get('contract_id') || params.get('contract');
    if (pre) {
      clientSel.value = pre;
      loadAnnualContracts(preContract).then(function () {
        if (preContract && document.getElementById('sel-contract')) {
          document.getElementById('sel-contract').value = String(preContract);
          generateAnnualReport();
        }
      });
    }
  }

  function fillAnnualContractOptions(contracts, preferId) {
    var contractSel = document.getElementById('sel-contract');
    if (!contractSel) return;
    if (!contracts || !contracts.length) {
      contractSel.innerHTML = '<option value="">لا توجد عقود في هذه الفترة</option>';
      return;
    }
    contractSel.innerHTML = '<option value="">اختر العقد / فترة التعاقد</option>' +
      contracts.map(function (ct) {
        var label = esc(ct.code) + ' — ' + esc(ct.start || '؟') + ' → ' + esc(ct.end || '؟');
        if (ct.status) label += ' (' + esc(ct.status) + ')';
        return '<option value="' + ct.id + '">' + label + '</option>';
      }).join('');
    if (preferId) {
      contractSel.value = String(preferId);
      if (contractSel.value !== String(preferId) && contracts[0]) {
        contractSel.value = String(contracts[0].id);
      }
    } else if (contracts.length === 1) {
      contractSel.value = String(contracts[0].id);
    }
  }

  async function loadAnnualContracts(preferId) {
    var clientId = document.getElementById('sel-client') && document.getElementById('sel-client').value;
    var year = document.getElementById('sel-year') && document.getElementById('sel-year').value;
    var contractSel = document.getElementById('sel-contract');
    if (!clientId) {
      if (contractSel) contractSel.innerHTML = '<option value="">اختر العميل أولاً</option>';
      return [];
    }
    try {
      var url = '/api/reports/client-annual/' + encodeURIComponent(clientId) +
        '?year=' + encodeURIComponent(year || '');
      var res = await fetch(url);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var data = await res.json();
      var contracts = data.contracts || [];
      fillAnnualContractOptions(contracts, preferId);
      return contracts;
    } catch (e) {
      console.error('Annual contracts load error:', e);
      if (contractSel) contractSel.innerHTML = '<option value="">تعذّر تحميل العقود</option>';
      return [];
    }
  }

  async function onAnnualClientChange() {
    await loadAnnualContracts();
    var contractSel = document.getElementById('sel-contract');
    if (contractSel && contractSel.value) generateAnnualReport();
    else hideAnnualReport();
  }

  async function onAnnualYearChange() {
    var prev = document.getElementById('sel-contract') && document.getElementById('sel-contract').value;
    await loadAnnualContracts(prev);
    var contractSel = document.getElementById('sel-contract');
    if (contractSel && contractSel.value) generateAnnualReport();
    else hideAnnualReport();
  }

  function hideAnnualReport() {
    var container = document.getElementById('report-container');
    var hint = document.getElementById('annual-empty-hint');
    if (container) container.style.display = 'none';
    if (hint) hint.style.display = '';
  }

  async function generateAnnualReport() {
    var clientId = document.getElementById('sel-client') && document.getElementById('sel-client').value;
    var year = document.getElementById('sel-year') && document.getElementById('sel-year').value;
    var contractId = document.getElementById('sel-contract') && document.getElementById('sel-contract').value;
    if (!clientId) {
      alert('اختر العميل أولاً');
      return;
    }
    if (!contractId) {
      alert('اختر العقد / فترة التعاقد');
      hideAnnualReport();
      return;
    }

    try {
      var url = '/api/reports/client-annual/' + encodeURIComponent(clientId) +
        '?contract_id=' + encodeURIComponent(contractId) +
        '&year=' + encodeURIComponent(year || '');
      var res = await fetch(url);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var data = await res.json();
      if (data.error) throw new Error(data.error);
      var c = data.customer || {};
      var stats = data.stats || {};
      var contract = data.contract || (data.contracts || [])[0] || {};

      setText('r-client-name', c.name || '—');
      setText('r-client-address', c.address || c.city || '—');
      setText('r-contract-no', contract.code || '—');
      setText('r-contract-period', (contract.start || '—') + ' → ' + (contract.end || '—'));

      var elevs = data.elevators || [];
      var elev = elevs[0] || {};
      var elevCodes = elevs.map(function (e) { return e.code; }).filter(Boolean).join('، ');
      setText('r-elev-type', elev.type || '—');
      setText('r-elev-model', elev.model || elev.brand || '—');
      setText('r-elev-capacity', elev.capacity || '—');
      setText('r-elev-no', elevCodes || elev.code || '—');

      setText('r-planned-visits', stats.planned_visits != null ? stats.planned_visits : '—');
      setText('r-done-visits', stats.done_visits != null ? stats.done_visits : '—');
      setText('r-compliance', (stats.compliance || 0) + '%');
      setText('r-faults-count', stats.total_faults != null ? stats.total_faults : '—');
      setText('r-faults-done', (stats.fault_rate || 0) + '%');
      setText('s-visits', stats.done_visits != null ? stats.done_visits : '—');
      setText('s-compliance', (stats.compliance || 0) + '%');
      setText('s-faults', stats.total_faults != null ? stats.total_faults : '—');
      setText('s-resolve', (stats.fault_rate || 0) + '%');

      var visitsEl = document.getElementById('r-visits-table');
      if (visitsEl) {
        visitsEl.innerHTML = (data.visits || []).length
          ? data.visits.map(function (v, i) {
            return '<tr><td class="num">' + (i + 1) + '</td><td class="num">' + esc(v.date) + '</td><td>' + esc(v.tech) + '</td><td>' + esc(v.type) + '</td><td>' + esc(v.works) + '</td><td>' + esc(v.status) + '</td></tr>';
          }).join('')
          : '<tr><td colspan="6" style="text-align:center;color:#aaa;padding:12px">لا توجد زيارات ضمن فترة هذا العقد</td></tr>';
      }

      var faultsEl = document.getElementById('r-faults-table');
      if (faultsEl) {
        faultsEl.innerHTML = (data.faults || []).length
          ? data.faults.map(function (f, i) {
            return '<tr><td class="num">' + (i + 1) + '</td><td>' + esc(f.type) + '</td><td class="num">' + esc(f.date) + '</td><td>' + esc(f.status) + '</td></tr>';
          }).join('')
          : '<tr><td colspan="4" style="text-align:center;color:#aaa;padding:12px">لا توجد أعطال ضمن فترة هذا العقد</td></tr>';
      }

      var partsEl = document.getElementById('r-parts-table');
      if (partsEl) {
        partsEl.innerHTML = (data.parts || []).length
          ? data.parts.map(function (p) {
            return '<tr><td>' + esc(p.description) + '</td><td class="num">' + esc(p.quantity) + '</td><td class="num">' + esc(p.date) + '</td></tr>';
          }).join('')
          : '<tr><td colspan="3" style="text-align:center;color:#aaa;padding:12px">لا توجد قطع ضمن فترة هذا العقد</td></tr>';
      }

      setText('r-print-date', 'تاريخ التقرير: ' + new Date().toLocaleDateString('ar-SA'));
      setText(
        'toolbar-title',
        'التقرير الختامي — ' + (c.name || '') + ' — ' + (contract.code || '') +
          ' (' + (contract.start || '') + ' → ' + (contract.end || '') + ')'
      );

      var container = document.getElementById('report-container');
      var hint = document.getElementById('annual-empty-hint');
      if (container) {
        container.style.display = 'block';
        container.scrollIntoView({ behavior: 'smooth' });
      }
      if (hint) hint.style.display = 'none';
    } catch (e) {
      console.error('Annual report error:', e);
      alert('تعذّر تحميل التقرير السنوي' + (e && e.message ? ': ' + e.message : ''));
    }
  }

  function exportReportExcel(reportId) {
    var apiUrl = REPORT_API[reportId];
    var data = __lcReportId === reportId ? __lcReportData : null;

    function download(rows) {
      if (!rows || !rows.length) return;
      var csv = rows.map(function (r) {
        return r.map(function (c) {
          var s = String(c == null ? '' : c).replace(/"/g, '""');
          return '"' + s + '"';
        }).join(',');
      }).join('\n');
      var a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' }));
      a.download = reportId + '.csv';
      a.click();
    }

    if (data && data.length) {
      var filtered = data.filter(function (row) { return rowPassesFilters(reportId, row); });
      download(filtered.map(function (row) { return reportRowCells(reportId, row); }));
      return;
    }

    if (!apiUrl) return;
    fetch(apiUrl)
      .then(function (r) { return r.json(); })
      .then(function (rows) {
        download(rows.map(function (row) { return reportRowCells(reportId, row); }));
      });
  }

  function exportDashboardExcel() {
    var d = __lcDashboardCache;
    if (!d) {
      alert('انتظر تحميل بيانات التقرير أولاً');
      return;
    }
    var rows = [
      ['مؤشرات الأداء الرئيسية', ''],
      ['إجمالي العملاء', d.customers],
      ['إجمالي المصاعد', d.elevators],
      ['العقود النشطة', d.contracts],
      ['إجمالي الإيرادات', d.revenue],
      ['إجمالي المصروفات', d.expenses],
      ['صافي الربح', (d.revenue || 0) - (d.expenses || 0)],
      [''],
      ['الإيرادات الشهرية', '', ''],
      ['الشهر', 'الإيرادات', 'المصروفات'],
    ];
    MONTHS_AR.forEach(function (m, i) {
      rows.push([m, (d.monthly_revenue || [])[i] || 0, (d.monthly_expenses || [])[i] || 0]);
    });
    var csv = rows.map(function (r) { return r.join(','); }).join('\n');
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' }));
    a.download = 'تقرير_الداشبورد.csv';
    a.click();
  }

  function hookExportExcel() {
    var reportId = document.body && document.body.getAttribute('data-report-id');
    var isDashboard = document.body && document.body.getAttribute('data-report-dashboard') === '1';
    var orig = global.exportExcel;
    global.exportExcel = function () {
      if (reportId && REPORT_API[reportId]) {
        exportReportExcel(reportId);
        return;
      }
      if (isDashboard) {
        exportDashboardExcel();
        return;
      }
      if (typeof orig === 'function') orig();
    };
  }

  global.loadReportData = loadReportData;
  global.loadDashboardReport = loadDashboardReport;
  global.generateAnnualReport = generateAnnualReport;
  global.onAnnualClientChange = onAnnualClientChange;
  global.onAnnualYearChange = onAnnualYearChange;
  global.generateReport = generateAnnualReport;
  global.exportReportExcel = exportReportExcel;
  global.loadData = function () { loadDashboardReport(); };

  function initReportsLive() {
    if (global.__lcReportsLiveReady) return;
    global.__lcReportsLiveReady = true;

    hookExportExcel();

    var bootId = global.__LC_REPORT_ID;
    var bootRows = global.__LC_REPORT_ROWS;
    if (bootId && REPORT_API[bootId] && Array.isArray(bootRows)) {
      applyReportPayload(bootId, bootRows);
    } else {
      var reportId = document.body && document.body.getAttribute('data-report-id');
      if (reportId && REPORT_API[reportId]) {
        loadReportData(reportId);
      }
    }

    if (document.body && document.body.getAttribute('data-report-dashboard') === '1') {
      var dashYear = document.getElementById('sel-year');
      if (dashYear && !dashYear.dataset.liveReady) {
        var cy = global.__LC_DASHBOARD_YEAR || new Date().getFullYear();
        dashYear.innerHTML = '';
        for (var y = cy; y >= cy - 5; y--) {
          dashYear.innerHTML += '<option value="' + y + '">' + y + '</option>';
        }
        dashYear.dataset.liveReady = '1';
      }
      if (global.Chart) loadDashboardReport();
      else global.addEventListener('load', function () { loadDashboardReport(); });
    }
    if (document.body && document.body.getAttribute('data-report-annual') === '1') {
      initAnnualReportSelectors();
    }
  }

  global.__lcInitReports = initReportsLive;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReportsLive);
  } else {
    initReportsLive();
  }
})(window);
