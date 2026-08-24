/**
 * واجهة حاسبة التسعير — مرتبطة بمشروع التركيب وعملاء LiftCore
 */
document.addEventListener('DOMContentLoaded', function () {
  var P = window.LiftCoreInstallPricing;
  if (!P) return;

  var cfg = window.__INSTALL_QUOTE__ || {};
  var saveUrl = cfg.saveUrl || '';
  var quoteCode = cfg.quoteCode || 'Q-____';
  var customers = cfg.customers || [];
  var machineBrands = cfg.machineBrands || {};
  var panelBrands = cfg.panelBrands || machineBrands;
  var customBrandOpt = cfg.customBrandOption || '__custom__';
  var customOriginOpt = cfg.customOriginOption || '__custom__';
  var noneOpt = cfg.noneOption || '__none__';
  var machineOrigins = cfg.machineOrigins || [];
  var companyLogoUrl = cfg.companyLogoUrl || '';
  var logoWidth = cfg.logoWidth || 150;
  var companyName = cfg.companyName || 'الشركة';
  var currentMode = 'new';
  var upgSelected = { commission: true };
  var hasBuiltRows = false;
  var draftKey = 'lc_install_quote_draft_' + (cfg.projectId || '0') + '_' + (cfg.quotationId || 'new');
  var draftTimer = null;

  function el(id) { return document.getElementById(id); }

  function markDrafting(on) {
    try {
      document.documentElement.setAttribute('data-lc-drafting', on ? '1' : '0');
    } catch (e) { /* ignore */ }
  }

  function collectDraft() {
    return {
      mode: currentMode,
      customer_id: el('cCustomer') ? el('cCustomer').value : '',
      valid_days: el('cValid') ? el('cValid').value : 30,
      labor: el('sumLabor') ? el('sumLabor').value : 0,
      transport: el('sumTrans') ? el('sumTrans').value : 0,
      other_costs: el('sumOther') ? el('sumOther').value : 0,
      profit_pct: el('sumProfitP') ? el('sumProfitP').value : 20,
      pay_count: getPayCount(),
      pay_installments: collectPayInstallments(),
      spec: currentMode === 'new' ? getNewSpec() : (currentMode === 'extend' ? getExtendSpec() : Object.assign(getUpgSpec(), { upg_selected: upgSelected })),
      lines: collectRows(),
      quote_type: currentMode,
      code: quoteCode,
      savedAt: Date.now(),
    };
  }

  function persistDraft() {
    try {
      var draft = collectDraft();
      if (!draft.lines || !draft.lines.length) return;
      sessionStorage.setItem(draftKey, JSON.stringify(draft));
      markDrafting(true);
    } catch (e) { /* ignore */ }
  }

  function scheduleDraftSave() {
    markDrafting(true);
    clearTimeout(draftTimer);
    draftTimer = setTimeout(persistDraft, 400);
  }

  function clearDraft() {
    try { sessionStorage.removeItem(draftKey); } catch (e) { /* ignore */ }
    markDrafting(false);
  }

  function restoreDraftIfNeeded() {
    try {
      var raw = sessionStorage.getItem(draftKey);
      if (!raw) return false;
      var s = JSON.parse(raw);
      if (!s || !s.lines || !s.lines.length) return false;
      if (s.savedAt && (Date.now() - s.savedAt) > 12 * 60 * 60 * 1000) {
        clearDraft();
        return false;
      }
      cfg.saved = s;
      markDrafting(true);
      return true;
    } catch (e) {
      return false;
    }
  }

  function toStoredCm(val) {
    var n = parseFloat(val);
    if (isNaN(n)) return val;
    if (n > 500) return Math.round(n / 10);
    return n;
  }
  function fmt(n) {
    n = Math.round(Number(n) || 0);
    return n.toLocaleString('en-US', { maximumFractionDigits: 0 }) + ' ر.س';
  }

  function fillStopsSelect(selId, def) {
    var sel = el(selId);
    if (!sel) return;
    var i, opts = '';
    for (i = 2; i <= 15; i++) {
      opts += '<option value="' + i + '"' + (i === (def || 6) ? ' selected' : '') + '>' + i + ' وقفات</option>';
    }
    sel.innerHTML = opts;
  }
  fillStopsSelect('sStops', cfg.stops || 6);
  fillStopsSelect('uStops', cfg.stops || 6);
  fillStopsSelect('eCurrentStops', 3);
  function fillAddedStopsSelect(def) {
    var sel = el('eAddedStops');
    if (!sel) return;
    var i, opts = '', pick = def || 2;
    for (i = 1; i <= 10; i++) {
      opts += '<option value="' + i + '"' + (i === pick ? ' selected' : '') + '>' + i + (i === 1 ? ' دور' : ' أدوار') + '</option>';
    }
    sel.innerHTML = opts;
  }
  fillAddedStopsSelect(2);

  function fillCustomerSelect() {
    if (typeof LcClientSelect !== 'undefined') {
      if (!LcClientSelect.isUpgraded('cCustomer')) {
        LcClientSelect.upgradeSelect('cCustomer', {
          customers: customers,
          onChange: onCustomerChange,
          placeholder: 'ابحث بالاسم أو الكود...',
        });
      }
      var defId = cfg.defaultCustomerId || (cfg.prefill && cfg.prefill.customer_id);
      LcClientSelect.setCustomers('cCustomer', customers, defId || '');
      onCustomerChange();
      return;
    }
    var sel = el('cCustomer');
    if (!sel) return;
    var html = '<option value="">— اختر عميلاً —</option>';
    var i;
    for (i = 0; i < customers.length; i++) {
      var c = customers[i];
      html += '<option value="' + c.id + '">' + c.code + ' — ' + c.name + '</option>';
    }
    sel.innerHTML = html;
    var defId = cfg.defaultCustomerId || (cfg.prefill && cfg.prefill.customer_id);
    if (defId) sel.value = String(defId);
    onCustomerChange();
  }

  function onCustomerChange() {
    var hidden = el('cCustomer');
    if (!hidden) return;
    var id = parseInt(hidden.value, 10);
    var c = null;
    var i;
    for (i = 0; i < customers.length; i++) {
      if (customers[i].id === id) { c = customers[i]; break; }
    }
    if (el('cName')) el('cName').value = c ? c.name : '';
    if (el('cPhone')) el('cPhone').value = c ? c.phone : '';
    if (el('cAddr')) el('cAddr').value = c ? c.address : '';
  }

  function isNoneVal(v) {
    return P.isNone ? P.isNone(v) : (v === noneOpt || v === 'بدون');
  }

  function initOriginSelect(selectId, customId, selectedOriginId, selectedCountry) {
    var sel = el(selectId);
    if (!sel) return;
    var pick = selectedOriginId || 'chinese';
    var html = '<option value="' + noneOpt + '"' + (pick === noneOpt ? ' selected' : '') + '>بدون</option>';
    var i, isCustom = selectedOriginId === customOriginOpt;
    for (i = 0; i < machineOrigins.length; i++) {
      var o = machineOrigins[i];
      html += '<option value="' + o.id + '"' + (o.id === pick ? ' selected' : '') + '>' + o.label + '</option>';
    }
    if (isCustom || (selectedCountry && !isKnownOrigin(selectedOriginId) && !isNoneVal(selectedOriginId))) {
      isCustom = true;
      html += '<option value="' + customOriginOpt + '" selected>+ بلد آخر...</option>';
    } else {
      html += '<option value="' + customOriginOpt + '">+ بلد آخر...</option>';
    }
    sel.innerHTML = html;
    if (pick === noneOpt) sel.value = noneOpt;
    toggleCustomOrigin(selectId, customId, isCustom ? selectedCountry : '');
  }

  function isKnownOrigin(originId) {
    var i;
    if (isNoneVal(originId) || originId === customOriginOpt) return false;
    for (i = 0; i < machineOrigins.length; i++) {
      if (machineOrigins[i].id === originId) return true;
    }
    return false;
  }

  function toggleCustomOrigin(selectId, customId, preset) {
    var sel = el(selectId);
    var inp = el(customId);
    if (!sel || !inp) return;
    var show = sel.value === customOriginOpt;
    inp.style.display = show ? '' : 'none';
    if (show && preset) inp.value = preset;
    if (!show && !inp.value) inp.value = '';
  }

  function resolveOrigin(selectId, customId) {
    var sel = el(selectId);
    if (!sel) return { id: 'chinese', country: '' };
    if (sel.value === noneOpt) {
      return { id: noneOpt, country: '' };
    }
    if (sel.value === customOriginOpt) {
      return { id: customOriginOpt, country: (el(customId) && el(customId).value.trim()) || '' };
    }
    return { id: sel.value, country: '' };
  }

  function fillBrandSelect(selectId, customId, brandsMap, originId, selectedBrand) {
    var sel = el(selectId);
    if (!sel) return;
    if (isNoneVal(originId)) {
      sel.innerHTML = '<option value="' + noneOpt + '" selected>بدون</option>';
      toggleCustomBrand(selectId, customId, '');
      return;
    }
    var brands = brandsMap[originId] || brandsMap.chinese || [];
    var html = '';
    var i, isCustom = false, matched = false;
    if (selectedBrand === noneOpt) {
      matched = true;
    }
    html += '<option value="' + noneOpt + '"' + (selectedBrand === noneOpt ? ' selected' : '') + '>بدون</option>';
    for (i = 0; i < brands.length; i++) {
      var pick = brands[i] === selectedBrand || (!selectedBrand && i === 0);
      if (brands[i] === selectedBrand) matched = true;
      html += '<option value="' + brands[i] + '"' + (pick && selectedBrand !== noneOpt ? ' selected' : '') + '>' + brands[i] + '</option>';
    }
    if (selectedBrand && selectedBrand !== noneOpt && brands.indexOf(selectedBrand) < 0 && selectedBrand !== customBrandOpt) {
      isCustom = true;
      matched = true;
    }
    html += '<option value="' + customBrandOpt + '"' + (isCustom ? ' selected' : '') + '>+ شركة أخرى...</option>';
    sel.innerHTML = html;
    if (!matched && brands.length && selectedBrand !== noneOpt) {
      sel.value = brands[0];
    }
    toggleCustomBrand(selectId, customId, isCustom ? selectedBrand : '');
  }

  function toggleCustomBrand(selectId, customId, preset) {
    var sel = el(selectId);
    var inp = el(customId);
    if (!sel || !inp) return;
    var show = sel.value === customBrandOpt;
    inp.style.display = show ? '' : 'none';
    if (show && preset) inp.value = preset;
    if (!show && !inp.value) inp.value = '';
  }

  function resolveBrand(selectId, customId) {
    var sel = el(selectId);
    if (!sel) return '';
    if (sel.value === noneOpt) return noneOpt;
    if (sel.value === customBrandOpt) {
      return (el(customId) && el(customId).value.trim()) || '';
    }
    return sel.value;
  }

  function updateCabinHint() {
    var hint = el('cabinCalcHint');
    if (!hint) return;
    var calc = P.calcCabinFromShaft(getNewSpec());
    if (calc.error) {
      hint.style.color = '#b45309';
      hint.textContent = '⚠️ ' + calc.error;
      return;
    }
    hint.style.color = '';
    var pct = Math.round((calc.priceFactor - 1) * 100);
    var adj = pct > 0 ? (' +' + pct + '%') : (pct < 0 ? (' ' + pct + '%') : '');
    hint.textContent = 'البئر: ' + (calc.shaftLabel || '—')
      + ' → كبينة محسوبة: ' + calc.label
      + (adj ? ' (تأثير السعر' + adj + ')' : ' (قياس قياسي)');
  }

  function stageCheckIds() {
    if (currentMode === 'extend') {
      return [
        { id: 'eStgRails', stage: P.STAGE_RAILS },
        { id: 'eStgCabin', stage: P.STAGE_CABIN },
        { id: 'eStgCtrl', stage: P.STAGE_CTRL },
      ];
    }
    return [
      { id: 'stgRails', stage: P.STAGE_RAILS },
      { id: 'stgCabin', stage: P.STAGE_CABIN },
      { id: 'stgCtrl', stage: P.STAGE_CTRL },
    ];
  }

  function getSelectedStages() {
    var checks = stageCheckIds();
    var out = [];
    var i, box;
    for (i = 0; i < checks.length; i++) {
      box = el(checks[i].id);
      if (box && box.checked) out.push(checks[i].stage);
    }
    return out;
  }

  function setSelectedStages(stages) {
    var checks = stageCheckIds();
    var wanted = stages && stages.length ? stages : checks.map(function (c) { return c.stage; });
    var i, box;
    for (i = 0; i < checks.length; i++) {
      box = el(checks[i].id);
      if (box) box.checked = wanted.indexOf(checks[i].stage) >= 0;
    }
    syncStagePickStyles();
  }

  function inferStagesFromLines(lines) {
    var known = [P.STAGE_RAILS, P.STAGE_CABIN, P.STAGE_CTRL];
    var found = [];
    var i, st;
    for (i = 0; i < lines.length; i++) {
      st = lines[i] && lines[i].stage;
      if (st && known.indexOf(st) >= 0 && found.indexOf(st) < 0) found.push(st);
    }
    return found;
  }

  function syncStagePickStyles() {
    document.querySelectorAll('.stage-picks .stage-pick').forEach(function (lab) {
      var box = lab.querySelector('input');
      lab.classList.toggle('on', !!(box && box.checked));
    });
  }

  function onStagePickChange(ev) {
    if (!getSelectedStages().length) {
      if (ev && ev.target) ev.target.checked = true;
      alert('اختر مرحلة واحدة على الأقل');
    }
    syncStagePickStyles();
    maybeRebuildBOM();
  }

  function getNewSpec() {
    var machineOrigin = resolveOrigin('sOrigin', 'sOriginCustom');
    var panelOrigin = resolveOrigin('sPanelOrigin', 'sPanelOriginCustom');
    var spec = {
      elevator_count: el('sElevCount') ? el('sElevCount').value : 1,
      stops: el('sStops').value,
      capacity: el('sCap').value,
      machine: el('sMachine').value,
      door: el('sDoor').value,
      cabin: el('sCabin').value,
      entrances: el('sEntr').value,
      floor_height: el('sFloorH').value,
      speed: el('sSpeed').value,
      shaft: el('sShaft').value,
      shaft_width: el('sShaftW') ? el('sShaftW').value : '',
      shaft_depth: el('sShaftD') ? el('sShaftD').value : '',
      machine_origin: machineOrigin.id,
      machine_origin_country: machineOrigin.country,
      machine_brand: resolveBrand('sBrand', 'sBrandCustom'),
      panel_origin: panelOrigin.id,
      panel_origin_country: panelOrigin.country,
      panel_brand: resolveBrand('sPanelBrand', 'sPanelBrandCustom'),
      include_stages: getSelectedStages(),
    };
    var cabinCalc = P.calcCabinFromShaft(spec);
    if (cabinCalc && !cabinCalc.error) {
      spec.cabin_width = cabinCalc.width;
      spec.cabin_depth = cabinCalc.depth;
    }
    return spec;
  }

  function getExtendSpec() {
    var machineOrigin = resolveOrigin('sOrigin', 'sOriginCustom');
    var panelOrigin = resolveOrigin('sPanelOrigin', 'sPanelOriginCustom');
    var currentStops = el('eCurrentStops') ? P.num(el('eCurrentStops').value) : 3;
    var addedStops = el('eAddedStops') ? P.num(el('eAddedStops').value) : 2;
    return {
      elevator_count: el('eElevCount') ? el('eElevCount').value : 1,
      current_stops: currentStops,
      added_stops: addedStops,
      stops: currentStops + addedStops,
      capacity: el('eCap') ? el('eCap').value : '630',
      door: el('eDoor') ? el('eDoor').value : 'tele',
      entrances: el('eEntr') ? el('eEntr').value : 1,
      floor_height: el('eFloorH') ? el('eFloorH').value : 300,
      machine_origin: machineOrigin.id,
      machine_origin_country: machineOrigin.country,
      machine_brand: resolveBrand('sBrand', 'sBrandCustom'),
      panel_origin: panelOrigin.id,
      panel_origin_country: panelOrigin.country,
      panel_brand: resolveBrand('sPanelBrand', 'sPanelBrandCustom'),
      include_stages: getSelectedStages(),
    };
  }

  function updateExtendHint() {
    var hint = el('extendHint');
    if (!hint) return;
    var cur = el('eCurrentStops') ? P.num(el('eCurrentStops').value) : 3;
    var add = el('eAddedStops') ? P.num(el('eAddedStops').value) : 2;
    hint.innerHTML = cur + ' وقفات قائمة + ' + add + ' دور = <b>' + (cur + add) + ' وقفات</b>';
  }

  function getUpgSpec() {
    var machineOrigin = resolveOrigin('sOrigin', 'sOriginCustom');
    var panelOrigin = resolveOrigin('sPanelOrigin', 'sPanelOriginCustom');
    return {
      elevator_count: el('uElevCount') ? el('uElevCount').value : 1,
      stops: el('uStops').value,
      capacity: el('uCap').value,
      machine_origin: machineOrigin.id,
      machine_origin_country: machineOrigin.country,
      machine_brand: resolveBrand('sBrand', 'sBrandCustom'),
      panel_origin: panelOrigin.id,
      panel_origin_country: panelOrigin.country,
      panel_brand: resolveBrand('sPanelBrand', 'sPanelBrandCustom'),
    };
  }

  var UNIT_OPTIONS = ['قطعة', 'متر', 'عدد', 'طقم', 'مقطوع', 'باب', 'كجم', 'م²', 'لفة', 'يوم', 'ساعة'];

  function escapeAttr(s) {
    return String(s == null ? '' : s).replace(/"/g, '&quot;').replace(/</g, '&lt;');
  }

  function unitCellHTML(current) {
    var cur = String(current == null ? 'قطعة' : current).trim() || 'قطعة';
    var opts = UNIT_OPTIONS.slice();
    var i, html;
    if (cur && opts.indexOf(cur) < 0 && cur !== '__custom__') {
      opts.unshift(cur);
    }
    html = '<div class="unit-cell">'
      + '<select class="f-unit" title="اختر الوحدة — أو أخرى لكتابة وحدة منطقتك">';
    for (i = 0; i < opts.length; i++) {
      html += '<option value="' + escapeAttr(opts[i]) + '"'
        + (opts[i] === cur ? ' selected' : '') + '>' + opts[i] + '</option>';
    }
    html += '<option value="__custom__">أخرى…</option>'
      + '</select>'
      + '<input class="f-unit-custom" type="text" placeholder="اكتب الوحدة" value="" style="display:none">'
      + '</div>';
    return html;
  }

  function readUnit(tr) {
    var sel = tr.querySelector('.f-unit');
    var custom = tr.querySelector('.f-unit-custom');
    if (!sel) return 'قطعة';
    if (sel.value === '__custom__') {
      return ((custom && custom.value) || '').trim() || 'قطعة';
    }
    return (sel.value || 'قطعة').trim();
  }

  function syncUnitCustomVisibility(tr, focusCustom) {
    var sel = tr.querySelector('.f-unit');
    var custom = tr.querySelector('.f-unit-custom');
    if (!sel || !custom) return;
    if (sel.value === '__custom__') {
      custom.style.display = 'block';
      if (focusCustom && !custom.value) custom.focus();
    } else {
      custom.style.display = 'none';
    }
  }

  function rowHTML(r) {
    return '<tr class="item-row" data-stage="' + escapeAttr(r.stage) + '">'
      + '<td><input class="w-name f-name" type="text" value="' + escapeAttr(r.name) + '"></td>'
      + '<td>' + unitCellHTML(r.unit) + '</td>'
      + '<td><input class="f-qty" type="number" min="0" step="1" value="' + Math.round(Number(r.qty) || 0) + '"></td>'
      + '<td><input class="f-price" type="number" min="0" step="1" value="' + Math.round(Number(r.price) || 0) + '"></td>'
      + '<td class="line-total">0</td>'
      + '<td><button type="button" class="pricing-del" title="حذف">✕</button></td>'
      + '</tr>';
  }

  function renderRows(rows) {
    hasBuiltRows = rows.length > 0;
    var stages = [], byStage = {}, i, r, html = '';
    for (i = 0; i < rows.length; i++) {
      r = rows[i];
      if (!byStage[r.stage]) { byStage[r.stage] = []; stages.push(r.stage); }
      byStage[r.stage].push(r);
    }
    for (i = 0; i < stages.length; i++) {
      html += '<tr class="stage-row" data-stage="' + stages[i] + '"><td colspan="6">📦 ' + stages[i] + '</td></tr>';
      var j, list = byStage[stages[i]];
      for (j = 0; j < list.length; j++) { html += rowHTML(list[j]); }
      html += '<tr class="stage-total" data-stage="' + stages[i] + '"><td colspan="4">إجمالي ' + stages[i] + '</td><td class="st-val" colspan="2">0</td></tr>';
    }
    el('itemsBody').innerHTML = html;
    bindTable();
    recalc();
  }

  function bindTable() {
    var body = el('itemsBody');
    var inputs = body.querySelectorAll('input');
    var selects = body.querySelectorAll('select.f-unit');
    var i;
    for (i = 0; i < inputs.length; i++) {
      inputs[i].addEventListener('input', function () {
        scheduleDraftSave();
        recalc();
      });
    }
    for (i = 0; i < selects.length; i++) {
      selects[i].addEventListener('change', function () {
        var tr = this.closest('tr');
        syncUnitCustomVisibility(tr, true);
        scheduleDraftSave();
        recalc();
      });
    }
    var dels = body.querySelectorAll('.pricing-del');
    for (i = 0; i < dels.length; i++) {
      dels[i].addEventListener('click', function () {
        this.closest('tr').remove();
        recalc();
      });
    }
    var rows = body.querySelectorAll('tr.item-row');
    for (i = 0; i < rows.length; i++) syncUnitCustomVisibility(rows[i]);
  }

  function collectRows() {
    var rows = el('itemsBody').querySelectorAll('tr.item-row');
    var out = [], i;
    for (i = 0; i < rows.length; i++) {
      out.push({
        stage: rows[i].getAttribute('data-stage') || '',
        name: rows[i].querySelector('.f-name').value || 'بند',
        unit: readUnit(rows[i]),
        qty: P.num(rows[i].querySelector('.f-qty').value),
        price: P.num(rows[i].querySelector('.f-price').value),
      });
    }
    return out;
  }

  var PAY_MAX = 8;
  var PAY_PRESETS = {
    1: [{ label: 'دفعة واحدة', pct: 100 }],
    2: [{ label: 'دفعة مقدمة', pct: 50 }, { label: 'عند التسليم', pct: 50 }],
    3: [{ label: 'دفعة مقدمة', pct: 50 }, { label: 'عند التوريد', pct: 40 }, { label: 'دفعة نهائية', pct: 10 }],
    4: [{ label: 'دفعة مقدمة', pct: 40 }, { label: 'عند التوريد', pct: 30 }, { label: 'بعد التركيب', pct: 20 }, { label: 'دفعة نهائية', pct: 10 }],
  };

  function defaultPayItems(count) {
    count = Math.max(1, Math.min(PAY_MAX, parseInt(count, 10) || 3));
    var i, each, labels, items;
    if (PAY_PRESETS[count]) {
      return PAY_PRESETS[count].map(function (r) { return { label: r.label, pct: r.pct }; });
    }
    labels = ['دفعة مقدمة'];
    for (i = 2; i < count; i++) labels.push('دفعة ' + i);
    labels.push('دفعة نهائية');
    each = Math.floor(100 / count);
    items = [];
    for (i = 0; i < count; i++) {
      items.push({
        label: labels[i],
        pct: i === count - 1 ? (100 - each * (count - 1)) : each,
      });
    }
    return items;
  }

  function getPayCount() {
    var n = el('payCount') ? parseInt(el('payCount').value, 10) : 3;
    if (isNaN(n) || n < 1) n = 3;
    if (n > PAY_MAX) n = PAY_MAX;
    return n;
  }

  function collectPayInstallments() {
    var box = el('payRows');
    if (!box) return defaultPayItems(getPayCount());
    var rows = box.querySelectorAll('.pay-install-row');
    var out = [], i, lab, pctEl;
    for (i = 0; i < rows.length; i++) {
      lab = rows[i].querySelector('.pay-label');
      pctEl = rows[i].querySelector('.pay-pct');
      out.push({
        label: lab ? String(lab.value || '').trim() : ('دفعة ' + (i + 1)),
        pct: P.num(pctEl ? pctEl.value : 0),
      });
    }
    return out;
  }

  function renderPayRows(items) {
    var box = el('payRows');
    if (!box) return;
    items = items && items.length ? items : defaultPayItems(3);
    var html = '', i;
    for (i = 0; i < items.length; i++) {
      html += '<div class="pay-install-row">'
        + '<input class="pay-label" type="text" value="' + escapeAttr(items[i].label || ('دفعة ' + (i + 1))) + '" placeholder="اسم الدفعة">'
        + '<input class="pay-pct" type="number" min="0" max="100" step="1" value="' + (items[i].pct || 0) + '">'
        + '</div>';
    }
    box.innerHTML = html;
    var inputs = box.querySelectorAll('input');
    for (i = 0; i < inputs.length; i++) {
      inputs[i].addEventListener('input', recalc);
    }
  }

  function applyPayCount(count) {
    count = Math.max(1, Math.min(PAY_MAX, parseInt(count, 10) || 3));
    if (el('payCount')) el('payCount').value = String(count);
    renderPayRows(defaultPayItems(count));
  }

  function itemsFromSaved(s) {
    if (s && s.pay_installments && s.pay_installments.length) return s.pay_installments;
    var adv = P.num(s && s.pay_advance_pct != null ? s.pay_advance_pct : 50);
    var sup = P.num(s && s.pay_supply_pct != null ? s.pay_supply_pct : 40);
    var fin = P.num(s && s.pay_final_pct != null ? s.pay_final_pct : 10);
    var items = [{ label: 'دفعة مقدمة', pct: adv }];
    if (sup > 0) items.push({ label: 'عند التوريد', pct: sup });
    if (fin > 0) items.push({ label: sup > 0 ? 'دفعة نهائية' : 'عند التسليم', pct: fin });
    return items;
  }

  function getPaymentPcts() {
    var items = collectPayInstallments();
    var n = items.length;
    var supply = 0, i;
    for (i = 1; i < n - 1; i++) supply += items[i].pct;
    return {
      count: n,
      advance: n ? items[0].pct : 0,
      supply: supply,
      final: n >= 2 ? items[n - 1].pct : 0,
      items: items,
    };
  }

  function paymentTermsText(pcts, grand) {
    var items = (pcts && pcts.items) ? pcts.items : collectPayInstallments();
    var html = '<b>شروط الدفع:</b><div class="q-pay-list">';
    var i, amt;
    for (i = 0; i < items.length; i++) {
      if (items[i].pct <= 0) continue;
      amt = Math.round(grand * items[i].pct / 100);
      html += '<div>' + items[i].pct + '% ' + (items[i].label || ('دفعة ' + (i + 1))) + ' (' + fmt(amt) + ')</div>';
    }
    return html + '</div>';
  }

  function recalcPaymentSchedule(grand) {
    var items = collectPayInstallments();
    var total = 0, i;
    for (i = 0; i < items.length; i++) total += items[i].pct;
    var totalEl = el('payPctTotal');
    var preview = el('payPreview');
    var payWarn = el('payWarnBox');
    if (totalEl) {
      totalEl.innerHTML = 'المجموع: <b>' + total + '%</b>';
      totalEl.style.color = total === 100 ? 'var(--text3)' : 'var(--danger)';
    }
    if (preview && grand > 0) {
      var html = '';
      for (i = 0; i < items.length; i++) {
        if (items[i].pct <= 0) continue;
        html += (html ? '<br>' : '') + escapeAttr(items[i].label || ('دفعة ' + (i + 1)))
          + ': <span class="amt">' + fmt(Math.round(grand * items[i].pct / 100)) + '</span>';
      }
      preview.innerHTML = html || 'أدخل نسب الدفعات';
    } else if (preview) {
      preview.innerHTML = 'أدخل البنود لحساب مبالغ الدفعات';
    }
    if (payWarn) {
      if (total !== 100) {
        payWarn.style.display = 'block';
        payWarn.textContent = '⚠️ مجموع نسب الدفعات يجب أن يساوي 100% (حالياً ' + total + '%)';
      } else {
        payWarn.style.display = 'none';
      }
    }
    return total === 100;
  }

  function recalc() {
    var rows = collectRows();
    var totals = P.calcTotals(
      rows,
      el('sumLabor').value,
      el('sumTrans').value,
      el('sumOther').value,
      el('sumProfitP').value
    );
    var body = el('itemsBody');
    var itemRows = body.querySelectorAll('tr.item-row');
    var stageSums = {}, i, lt;
    for (i = 0; i < itemRows.length; i++) {
      lt = P.num(itemRows[i].querySelector('.f-qty').value) * P.num(itemRows[i].querySelector('.f-price').value);
      itemRows[i].querySelector('.line-total').textContent = fmt(lt);
      var st = itemRows[i].getAttribute('data-stage');
      stageSums[st] = (stageSums[st] || 0) + lt;
    }
    var stRows = body.querySelectorAll('tr.stage-total');
    for (i = 0; i < stRows.length; i++) {
      var s = stRows[i].getAttribute('data-stage');
      stRows[i].querySelector('.st-val').textContent = fmt(stageSums[s] || 0);
    }
    el('sumMat').textContent = fmt(totals.materials_total);
    el('sumCost').textContent = fmt(totals.cost_total);
    el('sumProfit').textContent = fmt(totals.profit_amount);
    el('sumBefore').textContent = fmt(totals.before_tax);
    el('sumVat').textContent = fmt(totals.vat_amount);
    el('sumGrand').textContent = fmt(totals.grand_total);
    recalcPaymentSchedule(totals.grand_total);
    var warn = el('warnBox');
    var pp = P.num(el('sumProfitP').value);
    if (totals.materials_total > 0 && pp < 10) {
      warn.style.display = 'block';
      warn.textContent = '⚠️ هامش الربح أقل من 10% — تأكد أن السعر يغطي مخاطر المشروع';
    } else {
      warn.style.display = 'none';
    }
    if (hasBuiltRows || rows.length) scheduleDraftSave();
  }

  function buildNewBOM() {
    updateCabinHint();
    var result = P.buildNewBOM(getNewSpec());
    if (result.error) { alert(result.error); return; }
    currentMode = 'new';
    renderRows(result.rows);
    el('sumLabor').value = result.labor;
    el('sumTrans').value = el('sumTrans').value || 2000;
    recalc();
  }

  function maybeRebuildBOM() {
    if (!hasBuiltRows) return;
    if (currentMode === 'new') buildNewBOM();
    else if (currentMode === 'extend') buildExtendBOM();
    else if (currentMode === 'upgrade') buildUpgBOM();
  }

  function renderUpgCards() {
    var html = '', i, u, on;
    for (i = 0; i < P.UPG.length; i++) {
      u = P.UPG[i];
      on = upgSelected[u.id] ? ' on' : '';
      html += '<div class="upg-card' + on + '" data-id="' + u.id + '">'
        + '<div class="t"><span>' + u.name + '</span><span class="chk">' + (upgSelected[u.id] ? '✓' : '') + '</span></div>'
        + (u.desc ? '<div class="p">' + u.desc + '</div>' : '')
        + '</div>';
    }
    el('upgGrid').innerHTML = html;
    el('upgGrid').querySelectorAll('.upg-card').forEach(function (card) {
      card.addEventListener('click', function () {
        var id = this.getAttribute('data-id');
        upgSelected[id] = !upgSelected[id];
        renderUpgCards();
      });
    });
  }
  renderUpgCards();

  function buildUpgBOM() {
    var result = P.buildUpgradeBOM(getUpgSpec(), upgSelected);
    if (result.error) { alert(result.error); return; }
    currentMode = 'upgrade';
    renderRows(result.rows);
    el('sumLabor').value = result.labor;
    recalc();
  }

  function buildExtendBOM() {
    updateExtendHint();
    if (typeof P.buildExtendBOM !== 'function') { alert('حدّث الصفحة (Ctrl+F5)'); return; }
    var result = P.buildExtendBOM(getExtendSpec());
    if (result.error) { alert(result.error); return; }
    currentMode = 'extend';
    renderRows(result.rows);
    el('sumLabor').value = result.labor;
    el('sumTrans').value = el('sumTrans').value || 1500;
    recalc();
  }

  function addManualRow() {
    var body = el('itemsBody');
    var note = body.querySelector('.pricing-empty');
    if (note) { body.innerHTML = ''; }
    hasBuiltRows = true;
    var tr = document.createElement('tr');
    tr.className = 'item-row';
    tr.setAttribute('data-stage', 'بنود إضافية');
    tr.innerHTML = '<td><input class="w-name f-name" type="text" placeholder="اسم البند"></td>'
      + '<td>' + unitCellHTML('قطعة') + '</td>'
      + '<td><input class="f-qty" type="number" min="0" step="1" value="1"></td>'
      + '<td><input class="f-price" type="number" min="0" step="1" value="0"></td>'
      + '<td class="line-total">0</td>'
      + '<td><button type="button" class="pricing-del">✕</button></td>';
    body.appendChild(tr);
    bindTable();
    recalc();
  }

  function switchTab(mode) {
    el('paneNew').style.display = mode === 'new' ? '' : 'none';
    el('paneExtend').style.display = mode === 'extend' ? '' : 'none';
    el('paneUpg').style.display = mode === 'upgrade' ? '' : 'none';
    el('tabNewBtn').className = 'pricing-tab' + (mode === 'new' ? ' active' : '');
    if (el('tabExtendBtn')) el('tabExtendBtn').className = 'pricing-tab' + (mode === 'extend' ? ' active' : '');
    el('tabUpgBtn').className = 'pricing-tab' + (mode === 'upgrade' ? ' active' : '');
    currentMode = mode;
    hasBuiltRows = false;
    var empty = 'حدد المواصفات ثم اضغط «بناء قائمة القطع»';
    if (mode === 'extend') empty = 'حدد الوقفات الحالية والأدوار المضافة ثم اضغط «بناء قائمة إضافة الأدوار»';
    if (mode === 'upgrade') empty = 'اختر مكونات التحديث ثم اضغط «بناء قائمة التحديث»';
    el('itemsBody').innerHTML = '<tr><td colspan="6" class="pricing-empty">' + empty + '</td></tr>';
    el('sumLabor').value = 0;
    syncStagePickStyles();
    if (mode === 'extend') updateExtendHint();
    recalc();
  }

  function buildQuote() {
    var rows = collectRows();
    if (!rows.length) { alert('ابنِ قائمة البنود أولاً'); return; }
    var custSel = el('cCustomer');
    var custCode = '';
    if (custSel && custSel.value) {
      var ci = parseInt(custSel.value, 10);
      var j;
      for (j = 0; j < customers.length; j++) {
        if (customers[j].id === ci) { custCode = customers[j].code; break; }
      }
    }
    var labor = P.num(el('sumLabor').value);
    var trans = P.num(el('sumTrans').value);
    var other = P.num(el('sumOther').value);
    var pp = P.num(el('sumProfitP').value);
    var factor = 1 + pp / 100;
    var detailed = el('qDetailed').checked;
    var isUpg = currentMode === 'upgrade';
    var i, stageSums = {}, stagesOrder = [], itemsByStage = {};
    for (i = 0; i < rows.length; i++) {
      var r = rows[i];
      var sell = r.qty * r.price * factor;
      if (!stageSums[r.stage]) { stageSums[r.stage] = 0; stagesOrder.push(r.stage); itemsByStage[r.stage] = []; }
      stageSums[r.stage] += sell;
      itemsByStage[r.stage].push({ name: r.name, qty: r.qty, total: sell });
    }
    var laborSell = (labor + trans + other) * factor;
    var before = 0;
    for (i = 0; i < stagesOrder.length; i++) { before += stageSums[stagesOrder[i]]; }
    before += laborSell;
    var vat = before * 0.15;
    var grand = before + vat;
    var dateStr = new Date().toLocaleDateString('ar-SA');
    var validDays = P.num(el('cValid').value) || 30;
    var laborByStage = {};
    if (!isUpg && typeof P.splitLaborByStage === 'function') {
      var laborParts = P.splitLaborByStage(labor + trans + other, stagesOrder);
      for (i = 0; i < laborParts.length; i++) {
        laborByStage[laborParts[i].stage] = {
          label: laborParts[i].label,
          amount: laborParts[i].amount * factor,
        };
      }
    }
    var tbl = '<table class="q-tbl"><thead><tr><th style="width:55%">البيان</th><th>الكمية</th><th>الإجمالي (ر.س)</th></tr></thead><tbody>';
    for (i = 0; i < stagesOrder.length; i++) {
      var st2 = stagesOrder[i];
      var stageTotal = stageSums[st2] || 0;
      if (laborByStage[st2]) stageTotal += laborByStage[st2].amount;
      tbl += '<tr class="q-stage"><td>' + st2 + '</td><td></td><td>' + (detailed ? '' : fmt(stageTotal)) + '</td></tr>';
      if (detailed) {
        var k, its = itemsByStage[st2];
        for (k = 0; k < its.length; k++) {
          tbl += '<tr><td style="padding-right:22px">' + its[k].name + '</td><td>' + its[k].qty + '</td><td>' + fmt(its[k].total) + '</td></tr>';
        }
        if (laborByStage[st2]) {
          tbl += '<tr><td style="padding-right:22px">' + laborByStage[st2].label + '</td><td>1</td><td>' + fmt(laborByStage[st2].amount) + '</td></tr>';
        }
        tbl += '<tr class="q-stage"><td style="padding-right:22px">إجمالي ' + st2 + '</td><td></td><td>' + fmt(stageTotal) + '</td></tr>';
      } else if (laborByStage[st2]) {
        tbl += '<tr><td style="padding-right:22px">' + laborByStage[st2].label + '</td><td></td><td>' + fmt(laborByStage[st2].amount) + '</td></tr>';
      }
    }
    if (isUpg) {
      tbl += '<tr class="q-stage"><td>أعمال التركيب والتشغيل والتسليم</td><td></td><td>' + fmt(laborSell) + '</td></tr>';
    }
    tbl += '</tbody></table>';
    var specs = '';
    var quoteTitle = 'توريد وتركيب مصعد جديد';
    if (currentMode === 'upgrade') quoteTitle = 'تحديث مصعد قائم';
    if (currentMode === 'extend') quoteTitle = 'إضافة أدوار لمصعد قائم';
    if (currentMode === 'extend') {
      var spec = getExtendSpec();
      var cells = [];
      function pushPair(label, value) {
        if (!value && value !== 0) return;
        cells.push({ label: label, value: value });
      }
      pushPair('عدد المصاعد', spec.elevator_count || 1);
      pushPair('الوقفات الحالية', spec.current_stops + ' وقفات');
      pushPair('الأدوار المضافة', spec.added_stops + ' أدوار');
      pushPair('بعد الإضافة', spec.stops + ' وقفات');
      if (!isNoneVal(spec.capacity)) pushPair('الحمولة', spec.capacity + ' كجم');
      if (spec.include_stages && spec.include_stages.length && spec.include_stages.length < 3) {
        pushPair('نطاق العمل', spec.include_stages.join(' · '));
      }
      var specRows = '';
      var ci;
      for (ci = 0; ci < cells.length; ci += 2) {
        specRows += '<tr>';
        specRows += '<td>' + cells[ci].label + '</td><td>' + cells[ci].value + '</td>';
        if (cells[ci + 1]) {
          specRows += '<td>' + cells[ci + 1].label + '</td><td>' + cells[ci + 1].value + '</td>';
        } else {
          specRows += '<td></td><td></td>';
        }
        specRows += '</tr>';
      }
      specs = '<div class="q-sec"><h3>نطاق العمل</h3><table class="q-tbl"><tbody>' + specRows + '</tbody></table></div>';
    } else if (!isUpg) {
      var spec = getNewSpec();
      var cabinCalc = P.calcCabinFromShaft(Object.assign({}, spec, {
        capacity: isNoneVal(spec.capacity) ? 630 : spec.capacity,
      }));
      var shaftWcm = P.toCm(spec.shaft_width);
      var shaftDcm = P.toCm(spec.shaft_depth);
      var shaftTxt = (shaftWcm && shaftDcm) ? (shaftWcm + '×' + shaftDcm + ' سم') : '';
      var showCap = !isNoneVal(spec.capacity);
      var showSpeed = !isNoneVal(spec.speed);
      var showMachine = !isNoneVal(spec.machine);
      var showMachineOrigin = !isNoneVal(spec.machine_origin);
      var showPanelOrigin = !isNoneVal(spec.panel_origin);
      var showCabin = !isNoneVal(spec.cabin);
      var machineBrandTxt = isNoneVal(spec.machine_brand) ? '' : (spec.machine_brand || '');
      var panelBrandTxt = isNoneVal(spec.panel_brand) ? '' : (spec.panel_brand || '');
      var machineOriginTxt = showMachineOrigin
        ? (P.originDisplay(spec, 'machine_origin', 'machine_origin_country') + (machineBrandTxt ? (' ' + machineBrandTxt) : '')).trim()
        : '';
      var panelOriginTxt = showPanelOrigin
        ? (P.originDisplay(spec, 'panel_origin', 'panel_origin_country') + (panelBrandTxt ? (' ' + panelBrandTxt) : '')).trim()
        : '';
      var cells = [];
      function pushPair(label, value) {
        if (!value && value !== 0) return;
        cells.push({ label: label, value: value });
      }
      pushPair('عدد المصاعد', spec.elevator_count || 1);
      pushPair('عدد الوقفات', spec.stops + ' وقفات');
      if (showCap) pushPair('الحمولة', spec.capacity + ' كجم');
      if (showSpeed) pushPair('السرعة', spec.speed + ' م/ث');
      if (showMachine) {
        pushPair('نوع الماكينة', spec.machine === 'gearless' ? 'جيرلس MRL' : 'جير بغرفة ماكينة');
      }
      if (machineOriginTxt) pushPair('بلد منشئ الماكينة', machineOriginTxt);
      if (panelOriginTxt) pushPair('بلد منشئ اللوحة', panelOriginTxt);
      if (shaftTxt) pushPair('البئر الداخلي', shaftTxt);
      if (showCabin && cabinCalc && cabinCalc.label) pushPair('مقاس الكبينة', cabinCalc.label);
      if (showCabin && P.CABIN_NAMES[spec.cabin]) pushPair('تشطيب الكبينة', P.CABIN_NAMES[spec.cabin]);
      if (spec.include_stages && spec.include_stages.length && spec.include_stages.length < 3) {
        pushPair('نطاق العمل', spec.include_stages.join(' · '));
      }
      var specRows = '';
      var ci;
      for (ci = 0; ci < cells.length; ci += 2) {
        specRows += '<tr>';
        specRows += '<td>' + cells[ci].label + '</td><td>' + cells[ci].value + '</td>';
        if (cells[ci + 1]) {
          specRows += '<td>' + cells[ci + 1].label + '</td><td>' + cells[ci + 1].value + '</td>';
        } else {
          specRows += '<td></td><td></td>';
        }
        specRows += '</tr>';
      }
      if (specRows) {
        specs = '<div class="q-sec"><h3>المواصفات الفنية</h3><table class="q-tbl"><tbody>'
          + specRows + '</tbody></table></div>';
      }
    } else {
      specs = '<div class="q-sec"><h3>نطاق العمل</h3><div class="q-terms">تحديث مصعد قائم — '
        + (el('uElevCount') ? el('uElevCount').value : 1) + ' مصعد — '
        + el('uStops').value + ' وقفات.</div></div>';
    }
    var brandBlock = '<div class="brand">'
      + (companyLogoUrl
        ? '<img src="' + companyLogoUrl + '" alt="' + String(companyName).replace(/"/g, '&quot;') + '" style="width:' + logoWidth + 'px;max-height:72px;object-fit:contain">'
        : '')
      + '</div>';
    el('quoteSheet').innerHTML = ''
      + '<div class="q-head">' + brandBlock
      + '<div class="q-meta">رقم العرض: <b>' + quoteCode + '</b><br>التاريخ: <b>' + dateStr + '</b><br>الصلاحية: <b>' + validDays + ' يوم</b></div></div>'
      + '<div class="q-title">عرض سعر — ' + quoteTitle + '</div>'
      + '<div class="q-sec"><h3>بيانات العميل</h3><div class="q-terms">'
      + (custCode ? '<b>كود العميل:</b> ' + custCode + ' &nbsp; ' : '')
      + '<b>الاسم:</b> ' + (el('cName').value || '—') + ' &nbsp; <b>الجوال:</b> ' + (el('cPhone').value || '—') + ' &nbsp; <b>الموقع:</b> ' + (el('cAddr').value || '—') + '</div></div>'
      + specs + '<div class="q-sec"><h3>بنود العرض</h3>' + tbl + '</div>'
      + '<div class="q-totals"><div class="r"><span>الإجمالي قبل الضريبة</span><b>' + fmt(before) + '</b></div>'
      + '<div class="r"><span>ضريبة القيمة المضافة 15%</span><b>' + fmt(vat) + '</b></div>'
      + '<div class="g"><span>الإجمالي شامل الضريبة</span><span>' + fmt(grand) + '</span></div></div>'
      + '<div class="q-sec"><h3>الشروط</h3><div class="q-terms">'
      + paymentTermsText(getPaymentPcts(), grand) + '<br>'
      + '<b>الضمان:</b> سنة على أعمال التركيب + صيانة مجانية 12 شهراً.'
      + '</div></div>'
      + '<div class="q-sign"><div class="s">'
      + companySealHtml()
      + '<div class="ln">ختم وتوقيع الشركة</div></div><div class="s"><div class="ln">موافقة العميل</div></div></div>';
    el('quoteOverlay').classList.add('open');
  }

  function companySealHtml() {
    var stamp = cfg.companyStampUrl || '';
    var sign = cfg.companySignUrl || '';
    if (!stamp && !sign) return '';
    function imageStyle(kind, defaultWidth) {
      var width = Number(cfg['company' + kind + 'Width']) || defaultWidth;
      var offsetX = Number(cfg['company' + kind + 'OffsetX']) || 0;
      var offsetY = Number(cfg['company' + kind + 'OffsetY']) || 0;
      return '--doc-seal-width:' + width + 'px;--doc-seal-x:' + offsetX
        + 'px;--doc-seal-y:' + offsetY + 'px';
    }
    var html = '<div class="doc-company-seal q-company-seal">';
    if (stamp) {
      html += '<div class="doc-seal-item"><img src="' + stamp
        + '" alt="ختم الشركة" class="doc-seal-stamp" style="' + imageStyle('Stamp', 110)
        + '"><div class="doc-seal-caption">ختم الشركة</div></div>';
    }
    if (sign) {
      html += '<div class="doc-seal-item"><img src="' + sign
        + '" alt="توقيع الشركة" class="doc-seal-sign" style="' + imageStyle('Sign', 140)
        + '"><div class="doc-seal-caption">توقيع الشركة</div></div>';
    }
    return html + '</div>';
  }

  function saveQuote() {
    var rows = collectRows();
    if (!rows.length) { alert('ابنِ قائمة البنود أولاً'); return; }
    var customerId = el('cCustomer') ? parseInt(el('cCustomer').value, 10) : 0;
    if (!customerId) {
      alert('اختر عميلاً مسجّلاً من قائمة العملاء.\nإذا لم يكن موجوداً، أضفه من صفحة العملاء أولاً.');
      return;
    }
    var pcts = getPaymentPcts();
    var payTotal = 0, pi;
    for (pi = 0; pi < pcts.items.length; pi++) payTotal += pcts.items[pi].pct;
    if (payTotal !== 100) {
      alert('مجموع نسب الدفعات يجب أن يساوي 100% (حالياً ' + payTotal + '%).');
      return;
    }
    var payload = {
      quotation_id: cfg.quotationId || null,
      customer_id: customerId,
      quote_type: currentMode,
      client_name: el('cName').value,
      client_phone: el('cPhone').value,
      client_address: el('cAddr').value,
      valid_days: P.num(el('cValid').value) || 30,
      spec: currentMode === 'new' ? getNewSpec() : (currentMode === 'extend' ? getExtendSpec() : Object.assign(getUpgSpec(), { upg_selected: upgSelected })),
      labor: P.num(el('sumLabor').value),
      transport: P.num(el('sumTrans').value),
      other_costs: P.num(el('sumOther').value),
      profit_pct: P.num(el('sumProfitP').value),
      pay_advance_pct: pcts.advance,
      pay_supply_pct: pcts.supply,
      pay_final_pct: pcts.final,
      pay_count: pcts.count,
      pay_installments: pcts.items,
      lines: rows,
    };
    fetch(saveUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          quoteCode = data.code;
          cfg.quotationId = data.id;
          clearDraft();
          alert('تم حفظ العرض ' + data.code);
          if (window.history && window.location) {
            var u = new URL(window.location.href);
            u.searchParams.delete('new');
            u.searchParams.set('quotation_id', String(data.id));
            window.history.replaceState({}, '', u.pathname + u.search);
          }
        } else {
          alert(data.error || 'فشل الحفظ');
        }
      })
      .catch(function () { alert('خطأ في الاتصال بالخادم'); });
  }

  function loadSaved() {
    if (!cfg.saved) return;
    var s = cfg.saved;
    if (s.customer_id) {
      if (typeof LcClientSelect !== 'undefined' && LcClientSelect.isUpgraded('cCustomer')) {
        LcClientSelect.setCustomers('cCustomer', customers, s.customer_id);
      } else if (el('cCustomer')) {
        el('cCustomer').value = String(s.customer_id);
      }
    }
    onCustomerChange();
    if (el('cValid')) el('cValid').value = s.valid_days || 30;
    if (el('sumLabor')) el('sumLabor').value = s.labor || 0;
    if (el('sumTrans')) el('sumTrans').value = s.transport || 2000;
    if (el('sumOther')) el('sumOther').value = s.other_costs || 0;
    if (el('sumProfitP')) el('sumProfitP').value = s.profit_pct || 20;
    var payItems = itemsFromSaved(s);
    if (el('payCount')) el('payCount').value = String(payItems.length || 3);
    renderPayRows(payItems);
    currentMode = s.quote_type || 'new';
    if (currentMode === 'upgrade') switchTab('upgrade');
    if (currentMode === 'extend') switchTab('extend');
    if (s.spec) {
      initOriginSelect('sOrigin', 'sOriginCustom', s.spec.machine_origin || 'chinese', s.spec.machine_origin_country || '');
      fillBrandSelect('sBrand', 'sBrandCustom', machineBrands, s.spec.machine_origin || 'chinese', s.spec.machine_brand || '');
      initOriginSelect('sPanelOrigin', 'sPanelOriginCustom', s.spec.panel_origin || 'chinese', s.spec.panel_origin_country || '');
      fillBrandSelect('sPanelBrand', 'sPanelBrandCustom', panelBrands, s.spec.panel_origin || 'chinese', s.spec.panel_brand || '');
      if (el('sElevCount') && s.spec.elevator_count) el('sElevCount').value = s.spec.elevator_count;
      if (el('uElevCount') && s.spec.elevator_count) el('uElevCount').value = s.spec.elevator_count;
      if (el('eElevCount') && s.spec.elevator_count) el('eElevCount').value = s.spec.elevator_count;
      if (el('eCurrentStops') && s.spec.current_stops) el('eCurrentStops').value = s.spec.current_stops;
      if (el('eAddedStops') && s.spec.added_stops) el('eAddedStops').value = s.spec.added_stops;
      if (el('eCap') && s.spec.capacity) el('eCap').value = s.spec.capacity;
      if (el('eDoor') && s.spec.door) el('eDoor').value = s.spec.door;
      if (el('eEntr') && s.spec.entrances) el('eEntr').value = s.spec.entrances;
      if (el('eFloorH') && s.spec.floor_height) el('eFloorH').value = toStoredCm(s.spec.floor_height);
      if (el('sStops') && s.spec.stops) el('sStops').value = s.spec.stops;
      if (el('sCap') && s.spec.capacity) el('sCap').value = s.spec.capacity;
      if (el('sMachine') && s.spec.machine) el('sMachine').value = s.spec.machine;
      if (el('sDoor') && s.spec.door) el('sDoor').value = s.spec.door;
      if (el('sCabin') && s.spec.cabin) el('sCabin').value = s.spec.cabin;
      if (el('sEntr') && s.spec.entrances) el('sEntr').value = s.spec.entrances;
      if (el('sFloorH') && s.spec.floor_height) el('sFloorH').value = toStoredCm(s.spec.floor_height);
      if (el('sSpeed') && s.spec.speed) el('sSpeed').value = s.spec.speed;
      if (el('sShaft') && s.spec.shaft) el('sShaft').value = s.spec.shaft;
      if (el('sShaftW') && s.spec.shaft_width) el('sShaftW').value = toStoredCm(s.spec.shaft_width);
      if (el('sShaftD') && s.spec.shaft_depth) el('sShaftD').value = toStoredCm(s.spec.shaft_depth);
      if (s.spec.include_stages && s.spec.include_stages.length) {
        setSelectedStages(s.spec.include_stages);
      } else if (s.lines && s.lines.length && currentMode !== 'upgrade') {
        setSelectedStages(inferStagesFromLines(s.lines));
      }
      if (s.spec.upg_selected) upgSelected = s.spec.upg_selected;
    }
    if (currentMode === 'extend') updateExtendHint();
    if (s.lines && s.lines.length) renderRows(s.lines);
    quoteCode = s.code || quoteCode;
  }

  fillCustomerSelect();
  initOriginSelect('sOrigin', 'sOriginCustom', 'chinese', '');
  initOriginSelect('sPanelOrigin', 'sPanelOriginCustom', 'chinese', '');
  fillBrandSelect('sBrand', 'sBrandCustom', machineBrands, el('sOrigin') ? el('sOrigin').value : 'chinese', '');
  fillBrandSelect('sPanelBrand', 'sPanelBrandCustom', panelBrands, el('sPanelOrigin') ? el('sPanelOrigin').value : 'chinese', '');

  if (el('cCustomer') && (typeof LcClientSelect === 'undefined' || !LcClientSelect.isUpgraded('cCustomer'))) {
    el('cCustomer').addEventListener('change', onCustomerChange);
  }
  if (el('sOrigin')) {
    el('sOrigin').addEventListener('change', function () {
      toggleCustomOrigin('sOrigin', 'sOriginCustom', '');
      if (this.value !== customOriginOpt) {
        fillBrandSelect('sBrand', 'sBrandCustom', machineBrands, this.value, '');
      }
      maybeRebuildBOM();
    });
  }
  if (el('sPanelOrigin')) {
    el('sPanelOrigin').addEventListener('change', function () {
      toggleCustomOrigin('sPanelOrigin', 'sPanelOriginCustom', '');
      if (this.value !== customOriginOpt) {
        fillBrandSelect('sPanelBrand', 'sPanelBrandCustom', panelBrands, this.value, '');
      }
      maybeRebuildBOM();
    });
  }
  if (el('sOriginCustom')) el('sOriginCustom').addEventListener('input', maybeRebuildBOM);
  if (el('sPanelOriginCustom')) el('sPanelOriginCustom').addEventListener('input', maybeRebuildBOM);
  if (el('sBrand')) {
    el('sBrand').addEventListener('change', function () {
      toggleCustomBrand('sBrand', 'sBrandCustom', '');
      maybeRebuildBOM();
    });
  }
  if (el('sPanelBrand')) {
    el('sPanelBrand').addEventListener('change', function () {
      toggleCustomBrand('sPanelBrand', 'sPanelBrandCustom', '');
      maybeRebuildBOM();
    });
  }
  if (el('sBrandCustom')) el('sBrandCustom').addEventListener('input', maybeRebuildBOM);
  if (el('sPanelBrandCustom')) el('sPanelBrandCustom').addEventListener('input', maybeRebuildBOM);
  ['sShaftW', 'sShaftD', 'sCap', 'sElevCount', 'uElevCount', 'eElevCount'].forEach(function (id) {
    if (el(id)) el(id).addEventListener('input', function () { updateCabinHint(); maybeRebuildBOM(); });
  });
  ['eCurrentStops', 'eAddedStops', 'eCap', 'eDoor', 'eEntr', 'eFloorH'].forEach(function (id) {
    if (el(id)) el(id).addEventListener('change', function () { updateExtendHint(); maybeRebuildBOM(); });
  });
  if (el('eFloorH')) el('eFloorH').addEventListener('input', function () { updateExtendHint(); maybeRebuildBOM(); });
  updateCabinHint();
  updateExtendHint();

  el('tabNewBtn').addEventListener('click', function () { switchTab('new'); });
  if (el('tabExtendBtn')) el('tabExtendBtn').addEventListener('click', function () { switchTab('extend'); });
  el('tabUpgBtn').addEventListener('click', function () { switchTab('upgrade'); });
  el('buildBtn').addEventListener('click', buildNewBOM);
  if (el('buildExtBtn')) el('buildExtBtn').addEventListener('click', buildExtendBOM);
  el('buildUpgBtn').addEventListener('click', buildUpgBOM);
  ['stgRails', 'stgCabin', 'stgCtrl', 'eStgRails', 'eStgCabin', 'eStgCtrl'].forEach(function (id) {
    if (el(id)) el(id).addEventListener('change', onStagePickChange);
  });
  syncStagePickStyles();
  el('addRowBtn').addEventListener('click', addManualRow);
  el('previewBtn').addEventListener('click', buildQuote);
  el('saveBtn').addEventListener('click', saveQuote);
  el('printBtn').addEventListener('click', function () { window.print(); });
  el('closeQuoteBtn').addEventListener('click', function () { el('quoteOverlay').classList.remove('open'); });
  el('qDetailed').addEventListener('change', buildQuote);
  ['sumLabor', 'sumTrans', 'sumOther', 'sumProfitP'].forEach(function (id) {
    if (el(id)) el(id).addEventListener('input', recalc);
  });
  if (el('payCount')) {
    el('payCount').addEventListener('change', function () {
      applyPayCount(getPayCount());
      recalc();
    });
  }
  renderPayRows(defaultPayItems(el('payCount') ? el('payCount').value : 3));

  var restored = restoreDraftIfNeeded();
  if (cfg.saved) {
    loadSaved();
  } else if (cfg.prefill && cfg.prefill.customer_id) {
    if (typeof LcClientSelect !== 'undefined' && LcClientSelect.isUpgraded('cCustomer')) {
      LcClientSelect.setCustomers('cCustomer', customers, cfg.prefill.customer_id);
    } else if (el('cCustomer')) {
      el('cCustomer').value = String(cfg.prefill.customer_id);
    }
    onCustomerChange();
  }
  if (restored) {
    markDrafting(true);
  }
  recalc();
});
