/**
 * LiftCore — محضر تقرير العطل (مشترك بين الفني والمكتب)
 */
(function (global) {
  'use strict';

  const OUTCOME_CLASSES = {
    solved: 'active-success',
    partial: 'active-warning',
    needs_parts: 'active-danger',
  };

  function escHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function buildFaultTypes(types, selected, editable) {
    const root = document.getElementById('fault-types-root');
    if (!root) return;
    const sel = new Set(selected || []);
    root.innerHTML = types.map(function (t) {
      const id = 'ft-' + t.replace(/\s+/g, '-');
      const checked = sel.has(t) ? ' checked' : '';
      const dis = editable ? '' : ' disabled';
      return (
        '<label class="checkbox-item">' +
        '<input type="checkbox" value="' + escHtml(t) + '" id="' + escHtml(id) + '"' + checked + dis + '>' +
        ' ' + escHtml(t) + '</label>'
      );
    }).join('');
  }

  function collectFaultTypes() {
    const out = [];
    document.querySelectorAll('#fault-types-root input[type=checkbox]:checked').forEach(function (cb) {
      out.push(cb.value);
    });
    return out;
  }

  function applyFaultTypes(types) {
    const set = new Set(types || []);
    document.querySelectorAll('#fault-types-root input[type=checkbox]').forEach(function (cb) {
      cb.checked = set.has(cb.value);
    });
  }

  function addPartsRow(data) {
    const tbody = document.getElementById('parts-body');
    if (!tbody) return;
    const tr = document.createElement('tr');
    const row = data || { name: '', qty: 1, unit_price: 0 };
    tr.innerHTML =
      '<td><input type="text" class="part-name" placeholder="اسم القطعة" value="' + escHtml(row.name) + '"></td>' +
      '<td><input type="number" class="qty-input" min="1" value="' + (row.qty || 1) + '" style="direction:ltr"></td>' +
      '<td><input type="number" class="price-input" min="0" step="0.01" value="' + (row.unit_price || '') + '" style="direction:ltr"></td>' +
      '<td><input type="text" class="row-total" readonly style="direction:ltr;font-family:var(--font-en)"></td>' +
      '<td><button type="button" class="del-btn">×</button></td>';
    tbody.appendChild(tr);
    const del = tr.querySelector('.del-btn');
    if (del) del.addEventListener('click', function () { tr.remove(); calcTotals(); });
    tr.querySelectorAll('.qty-input,.price-input').forEach(function (inp) {
      inp.addEventListener('input', calcTotals);
    });
    calcTotals();
  }

  function buildPartsTable(rows, editable) {
    const tbody = document.getElementById('parts-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    const list = rows && rows.length ? rows : [{ name: '', qty: 1, unit_price: 0 }];
    list.forEach(function (r) { addPartsRow(r); });
    if (!editable) {
      tbody.querySelectorAll('input,button').forEach(function (el) {
        if (el.classList.contains('del-btn')) el.style.display = 'none';
        else el.readOnly = true;
      });
      const addBtn = document.getElementById('add-part-row');
      if (addBtn) addBtn.style.display = 'none';
    }
  }

  function calcTotals() {
    let partsTotal = 0;
    document.querySelectorAll('#parts-body tr').forEach(function (tr) {
      const qty = parseFloat(tr.querySelector('.qty-input')?.value) || 0;
      const price = parseFloat(tr.querySelector('.price-input')?.value) || 0;
      const rowTotal = qty * price;
      const rt = tr.querySelector('.row-total');
      if (rt) rt.value = rowTotal.toFixed(2);
      partsTotal += rowTotal;
    });
    const labor = parseFloat(document.getElementById('labor-cost')?.value) || 0;
    const subtotal = partsTotal + labor;
    const taxCalc = global.LiftCoreTaxCalc;
    const breakdown = taxCalc
      ? taxCalc.fromBeforeTax(subtotal, 15)
      : { before: subtotal, tax: subtotal * 0.15, total: subtotal * 1.15 };
    function set(id, val) {
      const el = document.getElementById(id);
      if (el) el.textContent = val.toLocaleString('en-US', { minimumFractionDigits: 2 }) + ' \u20C1';
    }
    set('total-parts', partsTotal);
    set('subtotal', breakdown.before);
    set('vat-amount', breakdown.tax);
    set('grand-total', breakdown.total);
  }

  function collectParts() {
    const out = [];
    document.querySelectorAll('#parts-body tr').forEach(function (tr) {
      const name = (tr.querySelector('.part-name')?.value || '').trim();
      const qty = parseFloat(tr.querySelector('.qty-input')?.value) || 0;
      const unit_price = parseFloat(tr.querySelector('.price-input')?.value) || 0;
      if (name || unit_price) out.push({ name: name, qty: qty || 1, unit_price: unit_price });
    });
    return out;
  }

  let outcomeTapInstalled = false;

  function setOutcome(btn) {
    if (!btn || btn.disabled) return;
    document.querySelectorAll('#status-group .status-btn').forEach(function (b) {
      b.className = 'status-btn';
      b.setAttribute('aria-pressed', 'false');
    });
    const val = btn.getAttribute('data-outcome');
    const cls = OUTCOME_CLASSES[val] || '';
    btn.className = 'status-btn ' + cls;
    btn.setAttribute('aria-pressed', 'true');
  }

  function initOutcomeButtons(editable) {
    if (!editable) return;
    document.querySelectorAll('#status-group .status-btn').forEach(function (btn) {
      btn.addEventListener('click', function () { setOutcome(btn); });
    });
    if (outcomeTapInstalled) return;
    outcomeTapInstalled = true;
    document.addEventListener('click', function (e) {
      const btn = e.target.closest('#status-group .status-btn:not(:disabled)');
      if (btn) setOutcome(btn);
    }, true);
  }

  function applyOutcome(val) {
    if (!val) return;
    const btn = document.querySelector('#status-group .status-btn[data-outcome="' + val + '"]');
    if (btn) setOutcome(btn);
  }

  function collectOutcome() {
    const sel = document.querySelector('#status-group .status-btn[aria-pressed="true"]');
    return sel ? sel.getAttribute('data-outcome') || '' : '';
  }

  const ratingTexts = ['', 'سيء', 'مقبول', 'جيد', 'جيد جداً', 'ممتاز ⭐'];

  function setRating(n) {
    document.querySelectorAll('#stars .star').forEach(function (s, i) {
      s.classList.toggle('active', i < n);
    });
    const el = document.getElementById('rating-text');
    if (el) el.textContent = ratingTexts[n] || 'اختر تقييماً';
    const hid = document.getElementById('customer-rating');
    if (hid) hid.value = n;
  }

  function initRating(editable) {
    if (!editable) return;
    document.querySelectorAll('#stars .star').forEach(function (star, i) {
      star.addEventListener('click', function () { setRating(i + 1); });
    });
  }

  function applyReportData(data) {
    if (!data) return;
    const meta = data.meta || {};
    const map = {
      'visit-date': meta.visit_date,
      'arrival-time': meta.arrival_time,
      'end-time': meta.end_time,
      'elevator-brand': meta.elevator_brand,
      'elevator-model': meta.elevator_model,
      'contract-type': meta.contract_type,
      'client-description': meta.client_description,
      'diagnosis': meta.diagnosis,
      'action-taken': meta.action_taken,
      'prevention': meta.prevention,
      'next-visit': meta.next_visit,
      'final-notes': meta.final_notes,
      'customer-comment': meta.customer_comment,
      'labor-cost': meta.labor_cost,
    };
    Object.entries(map).forEach(function (entry) {
      const el = document.getElementById(entry[0]);
      if (el && entry[1] != null && entry[1] !== '') el.value = entry[1];
    });
    applyFaultTypes(meta.fault_types || []);
    applyOutcome(meta.visit_outcome || '');
    if (meta.customer_rating) setRating(parseInt(meta.customer_rating, 10) || 0);
    if (global.LiftCoreChecklist) {
      global.LiftCoreChecklist.applySignatures(data.signatures || {});
      global.LiftCoreChecklist.applyPhotos(data.photos || []);
    }
    calcTotals();
  }

  function collectReportData() {
    function val(id) {
      const el = document.getElementById(id);
      return el ? el.value.trim() : '';
    }
    function num(id) {
      return parseFloat(document.getElementById(id)?.value) || 0;
    }
    return {
      meta: {
        visit_date: val('visit-date'),
        arrival_time: val('arrival-time'),
        end_time: val('end-time'),
        elevator_brand: val('elevator-brand'),
        elevator_model: val('elevator-model'),
        contract_type: val('contract-type'),
        client_description: val('client-description'),
        fault_types: collectFaultTypes(),
        diagnosis: val('diagnosis'),
        action_taken: val('action-taken'),
        prevention: val('prevention'),
        visit_outcome: collectOutcome(),
        next_visit: val('next-visit'),
        final_notes: val('final-notes'),
        customer_rating: parseInt(document.getElementById('customer-rating')?.value || '0', 10) || 0,
        customer_comment: val('customer-comment'),
        labor_cost: num('labor-cost'),
      },
      parts: collectParts(),
      signatures: global.LiftCoreChecklist ? {
        tech: global.LiftCoreChecklist.canvasDataUrl('sig-tech'),
        client: global.LiftCoreChecklist.canvasDataUrl('sig-client'),
      } : { tech: '', client: '' },
      photos: global.LiftCoreChecklist ? global.LiftCoreChecklist.collectPhotos() : [],
    };
  }

  global.LiftCoreFaultReport = {
    buildFaultTypes,
    buildPartsTable,
    addPartsRow,
    calcTotals,
    initOutcomeButtons,
    initRating,
    setRating,
    applyReportData,
    collectReportData,
  };
})(window);
