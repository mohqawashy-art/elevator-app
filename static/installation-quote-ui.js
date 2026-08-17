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
  var machineOrigins = cfg.machineOrigins || [];
  var currentMode = 'new';
  var upgSelected = { commission: true };
  var hasBuiltRows = false;

  function el(id) { return document.getElementById(id); }

  function toStoredCm(val) {
    var n = parseFloat(val);
    if (isNaN(n)) return val;
    if (n > 500) return Math.round(n / 10);
    return n;
  }
  function fmt(n) {
    n = Math.round(n);
    return n.toLocaleString('en-US') + ' ر.س';
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

  function initOriginSelect(selectId, customId, selectedOriginId, selectedCountry) {
    var sel = el(selectId);
    if (!sel) return;
    var html = '';
    var i, isCustom = selectedOriginId === customOriginOpt;
    for (i = 0; i < machineOrigins.length; i++) {
      var o = machineOrigins[i];
      html += '<option value="' + o.id + '"' + (o.id === selectedOriginId ? ' selected' : '') + '>' + o.label + '</option>';
    }
    if (isCustom || (selectedCountry && !isKnownOrigin(selectedOriginId))) {
      isCustom = true;
      html += '<option value="' + customOriginOpt + '" selected>+ بلد آخر...</option>';
    } else {
      html += '<option value="' + customOriginOpt + '">+ بلد آخر...</option>';
    }
    sel.innerHTML = html;
    toggleCustomOrigin(selectId, customId, isCustom ? selectedCountry : '');
  }

  function isKnownOrigin(originId) {
    var i;
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
    if (sel.value === customOriginOpt) {
      return { id: customOriginOpt, country: (el(customId) && el(customId).value.trim()) || '' };
    }
    return { id: sel.value, country: '' };
  }

  function fillBrandSelect(selectId, customId, brandsMap, originId, selectedBrand) {
    var sel = el(selectId);
    if (!sel) return;
    var brands = brandsMap[originId] || brandsMap.chinese || [];
    var html = '';
    var i, isCustom = false;
    for (i = 0; i < brands.length; i++) {
      html += '<option value="' + brands[i] + '"' + (brands[i] === selectedBrand ? ' selected' : '') + '>' + brands[i] + '</option>';
    }
    if (selectedBrand && brands.indexOf(selectedBrand) < 0) {
      isCustom = true;
    }
    html += '<option value="' + customBrandOpt + '"' + (isCustom ? ' selected' : '') + '>+ شركة أخرى...</option>';
    sel.innerHTML = html;
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

  function getNewSpec() {
    var machineOrigin = resolveOrigin('sOrigin', 'sOriginCustom');
    var panelOrigin = resolveOrigin('sPanelOrigin', 'sPanelOriginCustom');
    var spec = {
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
    };
    var cabinCalc = P.calcCabinFromShaft(spec);
    if (cabinCalc && !cabinCalc.error) {
      spec.cabin_width = cabinCalc.width;
      spec.cabin_depth = cabinCalc.depth;
    }
    return spec;
  }

  function getUpgSpec() {
    var machineOrigin = resolveOrigin('sOrigin', 'sOriginCustom');
    var panelOrigin = resolveOrigin('sPanelOrigin', 'sPanelOriginCustom');
    return {
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

  function rowHTML(r) {
    return '<tr class="item-row" data-stage="' + r.stage + '">'
      + '<td><input class="w-name f-name" type="text" value="' + String(r.name).replace(/"/g, '&quot;') + '"></td>'
      + '<td style="color:var(--text3);font-size:12px">' + r.unit + '</td>'
      + '<td><input class="f-qty" type="number" min="0" step="any" value="' + r.qty + '"></td>'
      + '<td><input class="f-price" type="number" min="0" step="any" value="' + r.price + '"></td>'
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
    var i;
    for (i = 0; i < inputs.length; i++) { inputs[i].addEventListener('input', recalc); }
    var dels = body.querySelectorAll('.pricing-del');
    for (i = 0; i < dels.length; i++) {
      dels[i].addEventListener('click', function () {
        this.closest('tr').remove();
        recalc();
      });
    }
  }

  function collectRows() {
    var rows = el('itemsBody').querySelectorAll('tr.item-row');
    var out = [], i;
    for (i = 0; i < rows.length; i++) {
      out.push({
        stage: rows[i].getAttribute('data-stage') || '',
        name: rows[i].querySelector('.f-name').value || 'بند',
        unit: rows[i].cells[1] ? rows[i].cells[1].textContent.trim() : '—',
        qty: P.num(rows[i].querySelector('.f-qty').value),
        price: P.num(rows[i].querySelector('.f-price').value),
      });
    }
    return out;
  }

  function getPaymentPcts() {
    return {
      advance: P.num(el('payAdvance') ? el('payAdvance').value : 50),
      supply: P.num(el('paySupply') ? el('paySupply').value : 40),
      final: P.num(el('payFinal') ? el('payFinal').value : 10),
    };
  }

  function paymentTermsText(pcts, grand) {
    var advAmt = Math.round(grand * pcts.advance / 100);
    var supAmt = Math.round(grand * pcts.supply / 100);
    var finAmt = Math.round(grand * pcts.final / 100);
    return '<b>شروط الدفع:</b>'
      + '<div class="q-pay-list">'
      + '<div>' + pcts.advance + '% دفعة مقدمة (' + fmt(advAmt) + ')</div>'
      + '<div>' + pcts.supply + '% عند التوريد (' + fmt(supAmt) + ')</div>'
      + '<div>' + pcts.final + '% عند التسليم (' + fmt(finAmt) + ')</div>'
      + '</div>';
  }

  function recalcPaymentSchedule(grand) {
    var pcts = getPaymentPcts();
    var total = pcts.advance + pcts.supply + pcts.final;
    var totalEl = el('payPctTotal');
    var preview = el('payPreview');
    var payWarn = el('payWarnBox');
    if (totalEl) {
      totalEl.innerHTML = 'المجموع: <b>' + total + '%</b>';
      totalEl.style.color = total === 100 ? 'var(--text3)' : 'var(--danger)';
    }
    if (preview && grand > 0) {
      preview.innerHTML = 'مقدمة: <span class="amt">' + fmt(Math.round(grand * pcts.advance / 100)) + '</span><br>'
        + 'توريد: <span class="amt">' + fmt(Math.round(grand * pcts.supply / 100)) + '</span><br>'
        + 'نهائية: <span class="amt">' + fmt(Math.round(grand * pcts.final / 100)) + '</span>';
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

  function addManualRow() {
    var body = el('itemsBody');
    var note = body.querySelector('.pricing-empty');
    if (note) { body.innerHTML = ''; }
    hasBuiltRows = true;
    var tr = document.createElement('tr');
    tr.className = 'item-row';
    tr.setAttribute('data-stage', 'بنود إضافية');
    tr.innerHTML = '<td><input class="w-name f-name" type="text" placeholder="اسم البند"></td>'
      + '<td style="color:var(--text3)">—</td>'
      + '<td><input class="f-qty" type="number" min="0" step="any" value="1"></td>'
      + '<td><input class="f-price" type="number" min="0" step="any" value="0"></td>'
      + '<td class="line-total">0</td>'
      + '<td><button type="button" class="pricing-del">✕</button></td>';
    body.appendChild(tr);
    bindTable();
    recalc();
  }

  function switchTab(mode) {
    var isNew = mode === 'new';
    el('paneNew').style.display = isNew ? '' : 'none';
    el('paneUpg').style.display = isNew ? 'none' : '';
    el('tabNewBtn').className = 'pricing-tab' + (isNew ? ' active' : '');
    el('tabUpgBtn').className = 'pricing-tab' + (isNew ? '' : ' active');
    currentMode = mode;
    hasBuiltRows = false;
    el('itemsBody').innerHTML = '<tr><td colspan="6" class="pricing-empty">' + (isNew
      ? 'حدد المواصفات ثم اضغط «بناء قائمة القطع»'
      : 'اختر مكونات التحديث ثم اضغط «بناء قائمة التحديث»') + '</td></tr>';
    el('sumLabor').value = 0;
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
    var tbl = '<table class="q-tbl"><thead><tr><th style="width:55%">البيان</th><th>الكمية</th><th>الإجمالي (ر.س)</th></tr></thead><tbody>';
    for (i = 0; i < stagesOrder.length; i++) {
      var st2 = stagesOrder[i];
      tbl += '<tr class="q-stage"><td>' + st2 + '</td><td></td><td>' + (detailed ? '' : fmt(stageSums[st2])) + '</td></tr>';
      if (detailed) {
        var k, its = itemsByStage[st2];
        for (k = 0; k < its.length; k++) {
          tbl += '<tr><td style="padding-right:22px">' + its[k].name + '</td><td>' + its[k].qty + '</td><td>' + fmt(its[k].total) + '</td></tr>';
        }
        tbl += '<tr class="q-stage"><td style="padding-right:22px">إجمالي ' + st2 + '</td><td></td><td>' + fmt(stageSums[st2]) + '</td></tr>';
      }
    }
    tbl += '<tr class="q-stage"><td>أعمال التركيب والتشغيل والتسليم</td><td></td><td>' + fmt(laborSell) + '</td></tr></tbody></table>';
    var specs = '';
    if (!isUpg) {
      var spec = getNewSpec();
      var cabinCalc = P.calcCabinFromShaft(spec);
      var shaftWcm = P.toCm(spec.shaft_width);
      var shaftDcm = P.toCm(spec.shaft_depth);
      var shaftTxt = (shaftWcm && shaftDcm) ? (shaftWcm + '×' + shaftDcm + ' سم') : '—';
      specs = '<div class="q-sec"><h3>المواصفات الفنية</h3><table class="q-tbl"><tbody>'
        + '<tr><td>عدد الوقفات</td><td>' + spec.stops + ' وقفات</td><td>الحمولة</td><td>' + spec.capacity + ' كجم</td></tr>'
        + '<tr><td>نوع الماكينة</td><td>' + (spec.machine === 'gearless' ? 'جيرلس MRL' : 'جير بغرفة ماكينة') + '</td><td>السرعة</td><td>' + spec.speed + ' م/ث</td></tr>'
        + '<tr><td>بلد منشئ الماكينة</td><td>' + P.originDisplay(spec, 'machine_origin', 'machine_origin_country') + ' ' + (spec.machine_brand || '') + '</td>'
        + '<td>بلد منشئ اللوحة</td><td>' + P.originDisplay(spec, 'panel_origin', 'panel_origin_country') + ' ' + (spec.panel_brand || '') + '</td></tr>'
        + '<tr><td>البئر الداخلي</td><td>' + shaftTxt + '</td><td>مقاس الكبينة</td><td>' + (cabinCalc.label || '—') + '</td></tr>'
        + '<tr><td>تشطيب الكبينة</td><td colspan="3">' + P.CABIN_NAMES[spec.cabin] + '</td></tr>'
        + '</tbody></table></div>';
    } else {
      specs = '<div class="q-sec"><h3>نطاق العمل</h3><div class="q-terms">تحديث مصعد قائم — ' + el('uStops').value + ' وقفات.</div></div>';
    }
    el('quoteSheet').innerHTML = ''
      + '<div class="q-head"><div class="co"><div class="nm">LiftCore</div><div class="sub">شركة تركيب وصيانة وتحديث المصاعد</div></div>'
      + '<div class="q-meta">رقم العرض: <b>' + quoteCode + '</b><br>التاريخ: <b>' + dateStr + '</b><br>الصلاحية: <b>' + validDays + ' يوم</b></div></div>'
      + '<div class="q-title">عرض سعر — ' + (isUpg ? 'تحديث مصعد قائم' : 'توريد وتركيب مصعد جديد') + '</div>'
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
      + '<div class="q-sign"><div class="s"><div class="ln">ختم وتوقيع الشركة</div></div><div class="s"><div class="ln">موافقة العميل</div></div></div>';
    el('quoteOverlay').classList.add('open');
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
    if (pcts.advance + pcts.supply + pcts.final !== 100) {
      alert('مجموع نسب الدفعات يجب أن يساوي 100%.\nمقدمة + توريد + نهائية = ' + (pcts.advance + pcts.supply + pcts.final) + '%');
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
      spec: currentMode === 'new' ? getNewSpec() : Object.assign(getUpgSpec(), { upg_selected: upgSelected }),
      labor: P.num(el('sumLabor').value),
      transport: P.num(el('sumTrans').value),
      other_costs: P.num(el('sumOther').value),
      profit_pct: P.num(el('sumProfitP').value),
      pay_advance_pct: pcts.advance,
      pay_supply_pct: pcts.supply,
      pay_final_pct: pcts.final,
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
    if (el('payAdvance')) el('payAdvance').value = s.pay_advance_pct != null ? s.pay_advance_pct : 50;
    if (el('paySupply')) el('paySupply').value = s.pay_supply_pct != null ? s.pay_supply_pct : 40;
    if (el('payFinal')) el('payFinal').value = s.pay_final_pct != null ? s.pay_final_pct : 10;
    currentMode = s.quote_type || 'new';
    if (currentMode === 'upgrade') switchTab('upgrade');
    if (s.spec) {
      initOriginSelect('sOrigin', 'sOriginCustom', s.spec.machine_origin || 'chinese', s.spec.machine_origin_country || '');
      fillBrandSelect('sBrand', 'sBrandCustom', machineBrands, s.spec.machine_origin || 'chinese', s.spec.machine_brand || '');
      initOriginSelect('sPanelOrigin', 'sPanelOriginCustom', s.spec.panel_origin || 'chinese', s.spec.panel_origin_country || '');
      fillBrandSelect('sPanelBrand', 'sPanelBrandCustom', panelBrands, s.spec.panel_origin || 'chinese', s.spec.panel_brand || '');
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
      if (s.spec.upg_selected) upgSelected = s.spec.upg_selected;
    }
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
  ['sShaftW', 'sShaftD', 'sCap'].forEach(function (id) {
    if (el(id)) el(id).addEventListener('input', function () { updateCabinHint(); maybeRebuildBOM(); });
  });
  updateCabinHint();

  el('tabNewBtn').addEventListener('click', function () { switchTab('new'); });
  el('tabUpgBtn').addEventListener('click', function () { switchTab('upgrade'); });
  el('buildBtn').addEventListener('click', buildNewBOM);
  el('buildUpgBtn').addEventListener('click', buildUpgBOM);
  el('addRowBtn').addEventListener('click', addManualRow);
  el('previewBtn').addEventListener('click', buildQuote);
  el('saveBtn').addEventListener('click', saveQuote);
  el('printBtn').addEventListener('click', function () { window.print(); });
  el('closeQuoteBtn').addEventListener('click', function () { el('quoteOverlay').classList.remove('open'); });
  el('qDetailed').addEventListener('change', buildQuote);
  ['sumLabor', 'sumTrans', 'sumOther', 'sumProfitP', 'payAdvance', 'paySupply', 'payFinal'].forEach(function (id) {
    if (el(id)) el(id).addEventListener('input', recalc);
  });

  loadSaved();
  if (!cfg.saved && cfg.prefill && cfg.prefill.customer_id) {
    if (typeof LcClientSelect !== 'undefined' && LcClientSelect.isUpgraded('cCustomer')) {
      LcClientSelect.setCustomers('cCustomer', customers, cfg.prefill.customer_id);
    } else if (el('cCustomer')) {
      el('cCustomer').value = String(cfg.prefill.customer_id);
    }
    onCustomerChange();
  }
  recalc();
});
