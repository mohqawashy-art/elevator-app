/* LiftCore — ملخص مدفوعات العميل وأقسام منفصلة */
(function (global) {
  'use strict';

  var TYPE_CLASS = {
    'إيراد': 'cp-type-rev',
    'قطع غيار': 'cp-type-parts',
    'فاتورة': 'cp-type-inv',
    'صيانة': 'cp-type-maint',
    'عطل': 'cp-type-fault',
  };

  var SECTION_TABS = [
    { key: 'contracts', label: 'العقود', entity: 'contract' },
    { key: 'visits', label: 'الزيارات', entity: 'visit' },
    { key: 'faults', label: 'الأعطال', entity: 'fault' },
    { key: 'parts', label: 'قطع الغيار', entity: 'part' },
  ];

  function fmt(n) {
    if (global.LiftCoreDisplay) return global.LiftCoreDisplay.fmtMoney(n);
    return (n || 0).toLocaleString('en-US', { maximumFractionDigits: 2 }) + ' \u20C1';
  }

  function L(s) {
    return global.LiftCoreDisplay ? global.LiftCoreDisplay.text(s) : s;
  }

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function fetchCustomerProfile(customerId, contractId) {
    var url = '/api/customers/' + customerId + '/profile';
    if (contractId) url += '?contract_id=' + contractId;
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error('profile fetch failed');
      return r.json();
    });
  }

  function renderFinancialBlock(data) {
    var f = data.financial || {};
    var c = data.contract;
    var period = c
      ? esc(c.start) + ' — ' + esc(c.end) + ' · ' + esc(c.code)
      : L('كل الفترات (لا يوجد عقد نشط)');

    var html = '<div class="cp-financial">';
    html += '<div class="cp-fin-title">' + L('المدفوعات خلال فترة التعاقد') + ' <span class="cp-fin-period">' + period + '</span></div>';
    html += '<div class="cp-fin-total"><span>' + L('إجمالي ما دفعه العميل') + '</span><span>' + fmt(f.total_paid) + '</span></div>';
    html += '<div class="cp-fin-row"><span>' + L('دفعات العقد / الفواتير') + '</span><span>' + fmt(f.contract_payments) + '</span></div>';
    html += '<div class="cp-fin-row"><span>' + L('قطع الغيار والتركيب') + '</span><span>' + fmt(f.parts_payments) + '</span></div>';
    if (f.other_payments > 0) {
      html += '<div class="cp-fin-row"><span>' + L('أعمال إضافية') + '</span><span>' + fmt(f.other_payments) + '</span></div>';
    }
    if (c) {
      html += '<div class="cp-fin-row"><span>' + L('قيمة العقد') + '</span><span>' + fmt(f.contract_value) + '</span></div>';
      html += '<div class="cp-fin-row"><span>' + L('المتبقي على العقد') + '</span><span style="color:var(--warning)">' + fmt(f.balance) + '</span></div>';
    }
    html += '</div>';
    return html;
  }

  function renderContractSelector(data, customerId, selectedId) {
    var list = data.contracts || [];
    if (list.length < 2) return '';
    var html = '<select class="cp-contract-sel" onchange="LiftCoreProfile.reloadCard(' + customerId + ', this.value)">';
    html += '<option value="">' + L('كل العقود / الفترة الحالية') + '</option>';
    list.forEach(function (ct) {
      html += '<option value="' + ct.id + '"' + (String(ct.id) === String(selectedId) ? ' selected' : '') + '>'
        + esc(ct.code) + ' (' + esc(ct.start) + ' — ' + esc(ct.end) + ')</option>';
    });
    html += '</select>';
    return html;
  }

  function renderSectionTable(rows, entityType, emptyLabel) {
    if (!rows || !rows.length) {
      return '<div class="cp-empty">' + L('لا توجد') + ' ' + esc(L(emptyLabel)) + '</div>';
    }
    var html = '<table class="cp-table cp-table-clickable"><thead><tr>'
      + '<th>' + L('التاريخ') + '</th><th>' + L('الكود') + '</th><th>' + L('البيان') + '</th><th>' + L('التفاصيل') + '</th><th>' + L('المبلغ') + '</th><th>' + L('الحالة') + '</th>'
      + '</tr></thead><tbody>';
    rows.forEach(function (row) {
      html += '<tr class="cp-click-row" data-entity="' + entityType + '" data-id="' + row.id + '" title="' + L('اضغط لعرض التفاصيل') + '">'
        + '<td class="cp-date">' + esc(row.date) + '</td>'
        + '<td class="cp-date" style="color:var(--accent)">' + esc(row.code) + '</td>'
        + '<td>' + esc(L(row.title)) + '</td>'
        + '<td style="font-size:11px;color:var(--text3)">' + esc(L(row.detail)) + '</td>'
        + '<td class="cp-amount">' + (row.amount > 0 ? fmt(row.amount) : '—') + '</td>'
        + '<td>' + esc(L(row.status || '—')) + '</td>'
        + '</tr>';
    });
    html += '</tbody></table>';
    return html;
  }

  function renderSectionTabs(data, activeTab) {
    activeTab = activeTab || 'contracts';
    var sections = data.sections || {};
    var counts = data.counts || {};
    var countMap = {
      contracts: (data.contracts || []).length,
      visits: counts.visits || 0,
      faults: counts.faults || 0,
      parts: counts.parts || 0,
    };

    var html = '<div class="cp-tabs" role="tablist">';
    SECTION_TABS.forEach(function (tab) {
      var n = countMap[tab.key] || 0;
      html += '<button type="button" class="cp-tab' + (activeTab === tab.key ? ' active' : '') + '"'
        + ' data-tab="' + tab.key + '" role="tab">'
        + L(tab.label) + ' <span class="cp-tab-count">' + n + '</span></button>';
    });
    html += '</div>';

    SECTION_TABS.forEach(function (tab) {
      var rows = sections[tab.key];
      if (tab.key === 'contracts' && (!rows || !rows.length)) {
        rows = (data.contracts || []).map(function (ct) {
          return {
            id: ct.id,
            code: ct.code,
            date: ct.start,
            title: ct.type || 'عقد',
            status: ct.status,
            detail: ct.end,
            amount: ct.total || 0,
          };
        });
      }
      html += '<div class="cp-tab-panel' + (activeTab === tab.key ? ' active' : '') + '" data-panel="' + tab.key + '">';
      html += renderSectionTable(rows, tab.entity, tab.label);
      html += '</div>';
    });
    return html;
  }

  function bindSectionTabs(container, customerId, parentEl) {
    if (!container) return;

    container.querySelectorAll('.cp-tab').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var key = btn.getAttribute('data-tab');
        container.querySelectorAll('.cp-tab').forEach(function (b) { b.classList.remove('active'); });
        container.querySelectorAll('.cp-tab-panel').forEach(function (p) { p.classList.remove('active'); });
        btn.classList.add('active');
        var panel = container.querySelector('[data-panel="' + key + '"]');
        if (panel) panel.classList.add('active');
        if (parentEl) parentEl._cpActiveTab = key;
      });
    });

    container.querySelectorAll('.cp-click-row').forEach(function (row) {
      row.addEventListener('click', function () {
        var entity = row.getAttribute('data-entity');
        var id = row.getAttribute('data-id');
        if (global.LiftCoreEntity && entity && id) {
          global.LiftCoreEntity.open(entity, id);
        }
      });
    });
  }

  function renderCustomerProfilePanel(data, options) {
    options = options || {};
    var html = '';
    if (options.showContractSelect !== false && data.contracts && data.contracts.length > 1) {
      html += renderContractSelector(data, data.customer.id, data.contract && data.contract.id);
    }
    if (options.showFinancial !== false) {
      html += renderFinancialBlock(data);
    }
    if (options.showSections !== false) {
      html += '<div class="cp-section">' + L('سجل العميل') + '</div>';
      html += '<div id="cp-sections-mount">' + renderSectionTabs(data, options.activeTab || 'contracts') + '</div>';
    } else if (options.showTimeline !== false) {
      html += renderTimelineLegacy(data, options.timelineLimit || 25);
    }
    return html;
  }

  function renderTimelineLegacy(data, limit) {
    var rows = (data.timeline || []).slice(0, limit);
    if (!rows.length) {
      return '<div class="cp-empty">' + L('لا توجد أحداث مسجّلة في هذه الفترة') + '</div>';
    }
    var html = '<table class="cp-table"><thead><tr>'
      + '<th>' + L('التاريخ') + '</th><th>' + L('النوع') + '</th><th>' + L('الكود') + '</th><th>' + L('البيان') + '</th><th>' + L('المبلغ') + '</th><th>' + L('الحالة') + '</th>'
      + '</tr></thead><tbody>';
    rows.forEach(function (row) {
      var cls = TYPE_CLASS[row.type] || 'cp-type-rev';
      html += '<tr>'
        + '<td class="cp-date">' + esc(row.date) + '</td>'
        + '<td><span class="cp-type ' + cls + '">' + esc(L(row.type)) + '</span></td>'
        + '<td class="cp-date" style="color:var(--accent)">' + esc(row.code) + '</td>'
        + '<td>' + esc(L(row.title)) + '</td>'
        + '<td class="cp-amount">' + (row.amount > 0 ? fmt(row.amount) : '—') + '</td>'
        + '<td>' + esc(L(row.status || '—')) + '</td>'
        + '</tr>';
    });
    html += '</tbody></table>';
    return html;
  }

  function loadIntoElement(el, customerId, contractId, options) {
    if (!el || !customerId) return Promise.resolve();
    options = options || {};
    var activeTab = el._cpActiveTab || options.activeTab || 'contracts';

    el.innerHTML = '<div class="cp-loading">' + L('جاري تحميل بيانات العميل...') + '</div>';
    return fetchCustomerProfile(customerId, contractId).then(function (data) {
      options.activeTab = activeTab;
      el.innerHTML = renderCustomerProfilePanel(data, options);
      var mount = el.querySelector('#cp-sections-mount');
      if (mount) bindSectionTabs(mount, customerId, el);
      if (global.LiftCoreI18n && global.LiftCoreDisplay && global.LiftCoreDisplay.isEn()) {
        global.LiftCoreI18n.apply('en');
      }
      return data;
    }).catch(function () {
      el.innerHTML = '<div class="cp-empty">' + L('تعذر تحميل بيانات العميل') + '</div>';
    });
  }

  function appendToView(viewBodyEl, customerId, contractId, options) {
    if (!viewBodyEl || !customerId) return Promise.resolve();
    options = options || {};
    options.showSections = false;
    options.timelineLimit = options.timelineLimit || 15;
    var mount = document.createElement('div');
    mount.className = 'customer-profile-append';
    mount.style.marginTop = '16px';
    mount.style.borderTop = '1px solid var(--border)';
    mount.style.paddingTop = '4px';
    viewBodyEl.appendChild(mount);
    return loadIntoElement(mount, customerId, contractId, options);
  }

  function reloadCard(customerId, contractId) {
    var el = document.getElementById('card-dynamic-data');
    if (!el) return;
    loadIntoElement(el, customerId, contractId || null, {
      showContractSelect: true,
      showSections: true,
    });
  }

  global.LiftCoreProfile = {
    fetch: fetchCustomerProfile,
    render: renderCustomerProfilePanel,
    loadIntoElement: loadIntoElement,
    appendToView: appendToView,
    reloadCard: reloadCard,
  };
})(typeof window !== 'undefined' ? window : this);
