(function () {
  'use strict';

  var CONTRACTS = window.__INSTALL_CONTRACTS__ || [];
  var CUSTOMERS = window.__INSTALL_CONTRACT_CUSTOMERS__ || [];
  var PROJECTS = window.__INSTALL_CONTRACT_PROJECTS__ || [];
  var QUOTES = window.__INSTALL_CONTRACT_QUOTATIONS__ || [];
  var NEXT_CODES = window.__INSTALL_CONTRACT_NEXT_CODES__ || {};
  var CSRF = window.__INSTALL_CONTRACT_CSRF__ || '';
  if (!CSRF) {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) CSRF = meta.getAttribute('content') || '';
  }

  var filtered = CONTRACTS.slice();
  var saving = false;
  var installmentRows = [];

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function fmtAmt(n) {
    return (Math.round(Number(n) || 0)).toLocaleString('en-US');
  }
  function getCustomer(id) {
    id = parseInt(id, 10);
    if (!id) return null;
    for (var i = 0; i < CUSTOMERS.length; i++) {
      if (CUSTOMERS[i].id === id) return CUSTOMERS[i];
    }
    return null;
  }

  var tableSort = window.LiftCoreTableSort ? LiftCoreTableSort.lazy({
    defaultCol: 'code',
    defaultDir: 'desc',
    dateCols: ['start_date', 'end_date'],
    numberCols: ['total', 'collected_amount', 'remaining_amount', 'progress_pct', 'days_left', 'installments_paid'],
    getters: {
      customer: function (c) { return c.customer || ''; },
      project_code: function (c) { return c.project_code || ''; },
      days_left: function (c) {
        var d = c.days_left;
        return d === null || d === undefined ? 999999 : d;
      },
    },
    onChange: function () { renderTable(filtered); },
  }) : null;

  var tablePager = window.LiftCorePagination ? LiftCorePagination.bind({
    pageSize: 15,
    container: '#page-btns',
    infoEl: '#table-info',
    onPageChange: function () { renderTable(filtered); },
  }) : null;

  function formatDays(c) {
    var d = c.days_left;
    if (d === null || d === undefined || !c.end_date) return '<span class="contract-days muted">—</span>';
    if (d < 0) return '<span class="contract-days expired">منتهي (' + Math.abs(d) + ')</span>';
    if (d <= 30) return '<span class="contract-days expiring">' + d + ' يوم</span>';
    return '<span class="contract-days active">' + d + ' يوم</span>';
  }

  function statusBadge(status) {
    var cls = 'badge-active';
    if (status === 'مكتمل') cls = 'badge-paid';
    else if (status === 'ملغي') cls = 'badge-cancelled';
    else if (status === 'مسودة') cls = 'badge-pending';
    return '<span class="badge ' + cls + '">' + esc(status || 'نشط') + '</span>';
  }

  function updateStats() {
    var total = CONTRACTS.length;
    var active = CONTRACTS.filter(function (c) { return c.status === 'نشط'; }).length;
    var done = CONTRACTS.filter(function (c) { return c.status === 'مكتمل'; }).length;
    var totalVal = CONTRACTS.reduce(function (s, c) { return s + (Number(c.total) || 0); }, 0);
    var remaining = CONTRACTS.reduce(function (s, c) { return s + (Number(c.remaining_amount) || 0); }, 0);
    if ($('stat-total')) $('stat-total').textContent = total;
    if ($('stat-active')) $('stat-active').textContent = active;
    if ($('stat-done')) $('stat-done').textContent = done;
    if ($('stat-total-val')) $('stat-total-val').textContent = fmtAmt(totalVal);
    if ($('stat-remaining')) $('stat-remaining').textContent = fmtAmt(remaining);
    if ($('contracts-count')) $('contracts-count').textContent = '(' + total + ' عقد)';
  }

  function filterTable() {
    var q = (($('search-input') && $('search-input').value) || '').trim().toLowerCase();
    var client = ($('f-client') && $('f-client').value) || '';
    var type = ($('f-type') && $('f-type').value) || '';
    var status = ($('f-status') && $('f-status').value) || '';
    filtered = CONTRACTS.filter(function (c) {
      if (client && c.customer !== client) return false;
      if (type && c.contract_type !== type) return false;
      if (status && c.status !== status) return false;
      if (!q) return true;
      var hay = [c.code, c.customer, c.project_code, c.contract_type, c.notes].join(' ').toLowerCase();
      return hay.indexOf(q) >= 0;
    });
    renderTable(filtered);
  }

  function renderTable(data) {
    if (tableSort) {
      data = tableSort.apply(data);
      tableSort.updateIndicators();
    }
    var pg = tablePager ? tablePager.apply(data, CONTRACTS.length) : { rows: data };
    var tbody = $('table-body');
    if (!tbody) return;
    if ($('table-info') && !tablePager) {
      $('table-info').textContent = 'عرض ' + data.length + ' من ' + CONTRACTS.length;
    }
    if (!pg.rows.length) {
      tbody.innerHTML = '<tr><td colspan="15" style="text-align:center;color:var(--text3);padding:28px">لا توجد عقود — اضغط «إضافة عقد» أو قبّل عرض سعر لبدء التنفيذ</td></tr>';
      return;
    }
    tbody.innerHTML = pg.rows.map(function (c) {
      var paid = Number(c.installments_paid) || 0;
      var totalInst = Number(c.installments_total) || 0;
      var instLabel = totalInst ? (paid + '/' + totalInst) : '—';
      var canPay = c.project_id && totalInst > 0 && paid < totalInst;
      return '<tr onclick="window.InstallContracts.view(' + c.id + ')">' +
        '<td class="td-code">' + esc(c.code) + '</td>' +
        '<td class="td-name">' + esc(c.customer) + '</td>' +
        '<td class="td-code">' + esc(c.project_code || '—') + '</td>' +
        '<td>' + esc(c.contract_type) + '</td>' +
        '<td style="direction:ltr;font-family:var(--font-en)">' + esc(c.start_date || '—') + '</td>' +
        '<td style="direction:ltr;font-family:var(--font-en)">' + esc(c.end_date || '—') + '</td>' +
        '<td>' + formatDays(c) + '</td>' +
        '<td><div style="font-size:11px;margin-bottom:3px">' + (c.progress_pct || 0) + '%</div><div class="ic-progress"><span style="width:' + (c.progress_pct || 0) + '%"></span></div></td>' +
        '<td class="td-amount" style="color:var(--success)">' + fmtAmt(c.collected_amount) + '</td>' +
        '<td class="td-amount" title="مسدّد من إجمالي الدفعات">' +
          '<span style="color:var(--success)">' + instLabel + '</span>' +
          (totalInst ? ' <span style="font-size:11px;color:var(--text3)">مسدّدة</span>' : '') +
        '</td>' +
        '<td class="td-amount" style="color:var(--warning)">' + fmtAmt(c.remaining_amount) + '</td>' +
        '<td class="td-amount">' + fmtAmt(c.total) + '</td>' +
        '<td>' + statusBadge(c.status) + '</td>' +
        '<td class="td-actions" onclick="event.stopPropagation()">' +
          '<a href="/installation/contracts/' + c.id + '" class="btn btn-primary btn-sm">فتح</a>' +
          (canPay ? '<a href="/installation/contracts/' + c.id + '#payments" class="btn btn-secondary btn-sm" style="color:var(--gold)">سداد</a>' : '') +
          '<button type="button" class="btn btn-secondary btn-sm" onclick="window.InstallContracts.edit(' + c.id + ')">تعديل</button>' +
        '</td>' +
      '</tr>';
    }).join('');
  }

  function initFilters() {
    var fClient = $('f-client');
    if (fClient) {
      CUSTOMERS.forEach(function (c) {
        var o = document.createElement('option');
        o.value = c.name;
        o.textContent = c.name;
        fClient.appendChild(o);
      });
    }
  }

  function nextCodeForType(type) {
    var prefix = (type || '').indexOf('تحديث') >= 0 ? 'CI-' : 'CI-';
    return NEXT_CODES[prefix] || NEXT_CODES['CI-'] || 'CI-00001';
  }

  function getQuote(id) {
    id = parseInt(id, 10);
    if (!id) return null;
    for (var i = 0; i < QUOTES.length; i++) {
      if (QUOTES[i].id === id) return QUOTES[i];
    }
    return null;
  }

  function currentTotal() {
    return parseFloat(($('f-total') && $('f-total').value) || 0) || 0;
  }

  function setInstallmentRows(rows) {
    installmentRows = (rows || []).map(function (r, i) {
      return {
        label: r.label || ('دفعة ' + (i + 1)),
        pct: parseFloat(r.pct || 0) || 0,
        amount: parseFloat(r.amount || 0) || 0,
      };
    });
    if (!installmentRows.length) {
      installmentRows = [{ label: 'دفعة واحدة', pct: 100, amount: currentTotal() }];
    }
    renderInstallmentRows();
  }

  function recalcInstallmentAmounts() {
    var total = currentTotal();
    var pctSum = installmentRows.reduce(function (s, r) { return s + (parseFloat(r.pct) || 0); }, 0);
    installmentRows.forEach(function (r) {
      var pct = parseFloat(r.pct) || 0;
      if (total > 0 && pct > 0) {
        r.amount = pctSum > 0 ? Math.round(total * pct / pctSum) : 0;
      }
    });
    var sum = installmentRows.reduce(function (s, r) { return s + (parseFloat(r.amount) || 0); }, 0);
    if (installmentRows.length && total > 0 && sum !== total) {
      installmentRows[installmentRows.length - 1].amount += (total - sum);
    }
    renderInstallmentRows(false);
  }

  function renderInstallmentRows(rebind) {
    var tbody = $('ic-inst-body');
    if (!tbody) return;
    if (rebind === undefined) rebind = true;
    tbody.innerHTML = installmentRows.map(function (r, idx) {
      return '<tr>' +
        '<td style="font-family:var(--font-en)">' + (idx + 1) + '</td>' +
        '<td><input type="text" data-inst-label="' + idx + '" value="' + esc(r.label) + '" placeholder="مثال: دفعة مقدمة / عند التوريد"></td>' +
        '<td style="width:90px"><input type="number" min="0" max="100" step="0.01" data-inst-pct="' + idx + '" value="' + (r.pct || 0) + '"></td>' +
        '<td style="width:120px"><input type="number" min="0" step="1" data-inst-amt="' + idx + '" value="' + (r.amount || 0) + '"></td>' +
        '<td style="width:36px">' + (installmentRows.length > 1 ? '<button type="button" class="inst-del" data-inst-del="' + idx + '">حذف</button>' : '') + '</td>' +
      '</tr>';
    }).join('');
    if (rebind) {
      tbody.querySelectorAll('[data-inst-label]').forEach(function (el) {
        el.addEventListener('input', function () {
          installmentRows[parseInt(el.getAttribute('data-inst-label'), 10)].label = el.value;
        });
      });
      tbody.querySelectorAll('[data-inst-pct]').forEach(function (el) {
        el.addEventListener('input', function () {
          installmentRows[parseInt(el.getAttribute('data-inst-pct'), 10)].pct = parseFloat(el.value) || 0;
          recalcInstallmentAmounts();
        });
      });
      tbody.querySelectorAll('[data-inst-amt]').forEach(function (el) {
        el.addEventListener('input', function () {
          installmentRows[parseInt(el.getAttribute('data-inst-amt'), 10)].amount = parseFloat(el.value) || 0;
          updateInstallmentSummary();
        });
      });
      tbody.querySelectorAll('[data-inst-del]').forEach(function (el) {
        el.addEventListener('click', function () {
          var i = parseInt(el.getAttribute('data-inst-del'), 10);
          installmentRows.splice(i, 1);
          if (!installmentRows.length) installmentRows = [{ label: 'دفعة واحدة', pct: 100, amount: currentTotal() }];
          renderInstallmentRows();
        });
      });
    }
    updateInstallmentSummary();
  }

  function updateInstallmentSummary() {
    var el = $('ic-inst-summary');
    if (!el) return;
    var sum = installmentRows.reduce(function (s, r) { return s + (parseFloat(r.amount) || 0); }, 0);
    el.textContent = installmentRows.length + ' دفعة — ' + fmtAmt(sum) + ' ر.س';
  }

  function collectInstallmentRows() {
    var tbody = $('ic-inst-body');
    if (!tbody) return installmentRows;
    tbody.querySelectorAll('[data-inst-label]').forEach(function (el) {
      installmentRows[parseInt(el.getAttribute('data-inst-label'), 10)].label = el.value;
    });
    tbody.querySelectorAll('[data-inst-pct]').forEach(function (el) {
      installmentRows[parseInt(el.getAttribute('data-inst-pct'), 10)].pct = parseFloat(el.value) || 0;
    });
    tbody.querySelectorAll('[data-inst-amt]').forEach(function (el) {
      installmentRows[parseInt(el.getAttribute('data-inst-amt'), 10)].amount = parseFloat(el.value) || 0;
    });
    return installmentRows;
  }

  function fillQuoteSelect(projectId, selectedId) {
    var sel = $('f-quote');
    if (!sel) return;
    sel.innerHTML = '<option value="">— بدون عرض (إدخال يدوي) —</option>';
    QUOTES.forEach(function (q) {
      if (projectId && String(q.project_id) !== String(projectId)) return;
      var o = document.createElement('option');
      o.value = q.id;
      o.textContent = q.code + ' — ' + (q.status || '') + ' (' + fmtAmt(q.total) + ' ر.س)';
      if (String(selectedId) === String(q.id)) o.selected = true;
      sel.appendChild(o);
    });
  }

  function applyQuote(quote) {
    if (!quote) return;
    $('f-type-sel').value = quote.contract_type || 'عقد تركيب';
    $('f-value').value = quote.value || '';
    $('f-tax-pct').value = quote.tax_pct || 15;
    $('f-tax-amount').value = quote.tax_amount || '';
    $('f-total').value = quote.total || '';
    loadTaxValues(quote.value, quote.tax_pct, quote.total);
    setInstallmentRows(quote.installments || []);
    var hint = $('f-quote-hint');
    if (hint) hint.textContent = 'مرتبط بعرض ' + quote.code + ' — ' + (quote.installments || []).length + ' دفعة';
  }

  function onProjectChange() {
    var cid = $('f-client-sel') && $('f-client-sel').value;
    var pid = $('f-project') && $('f-project').value;
    fillProjectSelect(cid, pid);
    fillQuoteSelect(pid, '');
    if ($('f-quote')) $('f-quote').value = '';
    if (pid) {
      var project = PROJECTS.find(function (p) { return String(p.id) === String(pid); });
      if (project && project.accepted_quotation_id) {
        fillQuoteSelect(pid, project.accepted_quotation_id);
        if ($('f-quote')) $('f-quote').value = String(project.accepted_quotation_id);
        onQuoteChange();
        return;
      }
      var latest = null;
      QUOTES.forEach(function (q) {
        if (String(q.project_id) !== String(pid)) return;
        if (!latest || q.id > latest.id) latest = q;
      });
      if (latest) {
        if ($('f-quote')) $('f-quote').value = String(latest.id);
        onQuoteChange();
      }
    }
  }

  function onQuoteChange() {
    var qid = $('f-quote') && $('f-quote').value;
    if (!qid) {
      var hint = $('f-quote-hint');
      if (hint) hint.textContent = 'اربط العقد بعرض سعر لتحميل القيمة وجدول الدفعات (دفعة مقدمة، عند التوريد، عند التسليم…)';
      return;
    }
    applyQuote(getQuote(qid));
  }

  function reloadFromQuote() {
    onQuoteChange();
  }

  function addInstallmentRow() {
    collectInstallmentRows();
    installmentRows.push({ label: 'دفعة ' + (installmentRows.length + 1), pct: 0, amount: 0 });
    recalcInstallmentAmounts();
  }

  function fillProjectSelect(customerId, selectedId) {
    var sel = $('f-project');
    if (!sel) return;
    sel.innerHTML = '<option value="">— مشروع جديد تلقائياً —</option>';
    PROJECTS.forEach(function (p) {
      if (String(p.customer_id) !== String(customerId)) return;
      if (p.has_contract && String(p.id) !== String(selectedId || '')) return;
      var o = document.createElement('option');
      o.value = p.id;
      o.textContent = p.code + (p.title ? ' — ' + p.title : '');
      if (String(selectedId) === String(p.id)) o.selected = true;
      sel.appendChild(o);
    });
  }

  function syncEndFromDuration() {
    var start = $('f-start') && $('f-start').value;
    var months = parseInt(($('f-duration') && $('f-duration').value) || '', 10);
    if (!start || !months) return;
    var parts = start.split('-');
    var d = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
    d.setMonth(d.getMonth() + months);
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    if ($('f-end')) $('f-end').value = y + '-' + m + '-' + day;
  }

  function loadTaxValues(value, taxPct, total) {
    var taxBlock = document.querySelector('#modal-add .lc-tax-block');
    if (!taxBlock || !window.LiftCoreTaxCalc) return;
    if (total && total > 0) {
      LiftCoreTaxCalc.loadInclusiveElement(taxBlock, total, taxPct || 15);
    } else if (value && value > 0) {
      LiftCoreTaxCalc.loadElement(taxBlock, value, taxPct || 15);
    } else {
      LiftCoreTaxCalc.resetElement(taxBlock);
    }
  }

  function resetForm() {
    $('f-code').value = nextCodeForType('عقد تركيب');
    $('f-type-sel').value = 'عقد تركيب';
    $('f-status-sel').value = 'نشط';
    $('f-start').value = new Date().toISOString().split('T')[0];
    $('f-duration').value = '12';
    $('f-end').value = '';
    $('f-value').value = '';
    $('f-tax-pct').value = '15';
    $('f-tax-amount').value = '';
    $('f-total').value = '';
    $('f-notes').value = '';
    fillProjectSelect('');
    fillQuoteSelect('');
    setInstallmentRows([{ label: 'دفعة واحدة', pct: 100, amount: 0 }]);
    var taxBlock = document.querySelector('#modal-add .lc-tax-block');
    if (taxBlock && window.LiftCoreTaxCalc) LiftCoreTaxCalc.resetElement(taxBlock);
  }

  function openModal(id) {
    $(id).classList.add('open');
  }
  function closeModal(id) {
    $(id).classList.remove('open');
  }

  function onClientChange() {
    var cid = $('f-client-sel') && $('f-client-sel').value;
    fillProjectSelect(cid);
    fillQuoteSelect('');
    if ($('f-quote')) $('f-quote').value = '';
    setInstallmentRows([{ label: 'دفعة واحدة', pct: 100, amount: currentTotal() }]);
  }

  function initClientSelect() {
    if (typeof LcClientSelect === 'undefined') return;
    LcClientSelect.upgradeSelect('f-client-sel', {
      customers: CUSTOMERS,
      onChange: onClientChange,
      placeholder: 'ابحث بالاسم أو الكود...',
    });
  }

  function calcTax() {
    var taxBlock = document.querySelector('#modal-add .lc-tax-block');
    if (taxBlock && window.LiftCoreTaxCalc) {
      var calc = taxBlock._lcTaxCalc || LiftCoreTaxCalc.bindFromElement(taxBlock);
      if (calc) calc.update();
    }
  }

  function openAdd() {
    $('modal-title').textContent = 'إضافة عقد تركيب';
    $('modal-add').dataset.editId = '';
    resetForm();
    syncEndFromDuration();
    if (typeof LcClientSelect !== 'undefined') {
      LcClientSelect.setCustomers('f-client-sel', CUSTOMERS, '');
    } else if ($('f-client-sel')) {
      $('f-client-sel').value = '';
    }
    openModal('modal-add');
  }

  function openEdit(id) {
    var c = CONTRACTS.find(function (x) { return x.id === id; });
    if (!c) return;
    $('modal-title').textContent = 'تعديل عقد ' + c.code;
    $('modal-add').dataset.editId = String(id);
    $('f-code').value = c.code;
    $('f-type-sel').value = c.contract_type || 'عقد تركيب';
    $('f-status-sel').value = c.status || 'نشط';
    $('f-start').value = c.start_date || '';
    $('f-duration').value = String(c.duration || 12);
    $('f-end').value = c.end_date || '';
    $('f-value').value = c.value || '';
    $('f-tax-pct').value = c.tax_pct || 15;
    $('f-tax-amount').value = c.tax_amount || '';
    $('f-total').value = c.total || '';
    $('f-notes').value = c.notes || '';
    if (typeof LcClientSelect !== 'undefined') {
      LcClientSelect.setCustomers('f-client-sel', CUSTOMERS, c.customer_id);
    }
    fillProjectSelect(c.customer_id, c.project_id);
    fillQuoteSelect(c.project_id, c.quotation_id);
    if (c.quotation_id && $('f-quote')) $('f-quote').value = String(c.quotation_id);
    if (c.installments && c.installments.length) {
      setInstallmentRows(c.installments);
    } else {
      setInstallmentRows([{ label: 'دفعة واحدة', pct: 100, amount: c.total || 0 }]);
    }
    loadTaxValues(c.value, c.tax_pct, c.total);
    openModal('modal-add');
  }

  function saveContract() {
    if (saving) return;
    var taxBlock = document.querySelector('#modal-add .lc-tax-block');
    if (taxBlock && window.LiftCoreTaxCalc) {
      var calc = taxBlock._lcTaxCalc || LiftCoreTaxCalc.bindFromElement(taxBlock);
      if (calc) calc.update();
    }
    var editId = $('modal-add').dataset.editId;
    var fd = new FormData();
    fd.append('csrf_token', CSRF);
    fd.append('customer_id', ($('f-client-sel') && $('f-client-sel').value) || '');
    fd.append('project_id', ($('f-project') && $('f-project').value) || '');
    fd.append('quotation_id', ($('f-quote') && $('f-quote').value) || '');
    fd.append('contract_type', $('f-type-sel').value);
    fd.append('status', $('f-status-sel').value);
    fd.append('start_date', $('f-start').value);
    fd.append('duration_months', $('f-duration').value);
    fd.append('end_date', $('f-end').value);
    fd.append('value', $('f-value').value);
    fd.append('tax_pct', $('f-tax-pct').value);
    fd.append('tax_amount', $('f-tax-amount').value);
    fd.append('total', $('f-total').value);
    fd.append('notes', $('f-notes').value);
    collectInstallmentRows();
    fd.append('installments_json', JSON.stringify(installmentRows.map(function (r) {
      return { label: r.label, pct: r.pct, amount: r.amount };
    })));
    var url = editId
      ? '/installation/contracts/' + editId + '/edit'
      : '/installation/contracts/add';
    saving = true;
    fetch(url, {
      method: 'POST',
      body: fd,
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' },
      credentials: 'same-origin',
    }).then(function (r) {
      return r.text().then(function (text) {
        var j = null;
        try { j = text ? JSON.parse(text) : null; } catch (e) { j = null; }
        return { ok: r.ok, body: j, status: r.status, raw: text };
      });
    })
      .then(function (res) {
        saving = false;
        if (!res.body) {
          alert(res.status === 403 ? 'انتهت الجلسة أو رُفض الطلب — حدّث الصفحة وسجّل الدخول' : 'تعذّر حفظ العقد (استجابة غير متوقعة)');
          return;
        }
        if (!res.ok || !res.body.ok) {
          alert((res.body && res.body.message) || 'تعذّر حفظ العقد');
          return;
        }
        window.location.reload();
      })
      .catch(function () {
        saving = false;
        alert('تعذّر الاتصال بالخادم');
      });
  }

  window.InstallContracts = {
    openAdd: openAdd,
    edit: openEdit,
    view: function (id) { window.location.href = '/installation/contracts/' + id; },
    save: saveContract,
    close: function (id) { closeModal(id || 'modal-add'); },
    filter: filterTable,
    calcTax: calcTax,
    syncEnd: syncEndFromDuration,
    onProjectChange: onProjectChange,
    onQuoteChange: onQuoteChange,
    reloadFromQuote: reloadFromQuote,
    addInstallmentRow: addInstallmentRow,
  };

  document.addEventListener('DOMContentLoaded', function () {
    try {
      if (tableSort) tableSort.bindHeaders();
      initFilters();
      initClientSelect();
      updateStats();
      renderTable(filtered);
      var params = new URLSearchParams(window.location.search);
      if (params.get('action') === 'add') {
        openAdd();
        history.replaceState(null, '', window.location.pathname);
      }
    } catch (e) {
      console.error('install contracts boot', e);
    }
  });
})();
