/* LiftCore — كروت تفاصيل الزيارات / الأعطال / قطع الغيار / العقود */
(function (global) {
  'use strict';

  var API = {
    visit: '/api/maintenance-visits/',
    fault: '/api/faults/',
    part: '/api/parts-billing/',
    contract: '/api/contracts/',
  };

  var STATUS_BADGE = {
    'نشط': 'badge-active', 'مكتملة': 'badge-active', 'مجدولة': 'badge-active', 'مغلق': 'badge-active',
    'غير نشط': 'badge-cancelled', 'ملغاة': 'badge-cancelled', 'ملغي': 'badge-cancelled',
    'منتهي': 'badge-expired', 'متأخرة': 'badge-expired', 'مفتوح': 'badge-expired',
    'قيد المعالجة': 'badge-expiring', 'على وشك الانتهاء': 'badge-expiring',
  };

  var PRIORITY_BADGE = {
    'عادية': 'badge-active', 'عاجلة': 'badge-expiring', 'حرجة': 'badge-expired',
  };

  var INV_BADGE = {
    'مدفوع': 'badge-active', 'مدفوع جزئياً': 'badge-expiring',
    'غير مدفوع': 'badge-unpaid', 'متأخر': 'badge-expired',
  };

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function fmt(n) {
    return (n || 0).toLocaleString('ar-SA', { maximumFractionDigits: 2 });
  }

  function badge(cls, text) {
    return '<span class="badge ' + (cls || 'badge-active') + '">' + esc(text) + '</span>';
  }

  function ensureModal() {
    if (document.getElementById('modal-entity-detail')) return;
    var html = '<div class="modal-overlay" id="modal-entity-detail" style="z-index:250">'
      + '<div class="modal" style="max-width:720px;max-height:90vh;overflow:hidden;display:flex;flex-direction:column">'
      + '<div class="modal-head"><div class="modal-title" id="entity-detail-title">التفاصيل</div>'
      + '<button class="modal-close" type="button" onclick="LiftCoreEntity.close()">'
      + '<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">'
      + '<line x1="2" y1="2" x2="12" y2="12"/><line x1="12" y1="2" x2="2" y2="12"/></svg>'
      + '</button></div>'
      + '<div class="modal-body" id="entity-detail-body" style="overflow-y:auto"></div>'
      + '</div></div>';
    document.body.insertAdjacentHTML('beforeend', html);
  }

  function openModal(title, bodyHtml) {
    ensureModal();
    document.getElementById('entity-detail-title').textContent = title;
    document.getElementById('entity-detail-body').innerHTML = bodyHtml;
    document.getElementById('modal-entity-detail').classList.add('open');
  }

  function close() {
    var m = document.getElementById('modal-entity-detail');
    if (m) m.classList.remove('open');
  }

  function renderVisit(v) {
    return '<div class="view-grid">'
      + '<div class="view-section">بيانات الزيارة</div>'
      + '<div class="view-item"><div class="view-label">الكود</div><div class="view-val" style="font-family:var(--font-en)">' + esc(v.code) + '</div></div>'
      + '<div class="view-item"><div class="view-label">العميل</div><div class="view-val">' + esc(v.customer) + '</div></div>'
      + '<div class="view-item"><div class="view-label">المصعد</div><div class="view-val" style="font-family:var(--font-en)">' + esc(v.elevator) + '</div></div>'
      + '<div class="view-item"><div class="view-label">الفني</div><div class="view-val">' + esc(v.technician) + '</div></div>'
      + '<div class="view-item"><div class="view-label">نوع الزيارة</div><div class="view-val">' + esc(v.visit_type) + '</div></div>'
      + '<div class="view-item"><div class="view-label">التاريخ</div><div class="view-val" style="direction:ltr">' + esc(v.visit_date) + '</div></div>'
      + '<div class="view-item"><div class="view-label">الوقت</div><div class="view-val" style="direction:ltr">' + esc(v.visit_time || '—') + '</div></div>'
      + '<div class="view-item"><div class="view-label">الأولوية</div><div class="view-val">' + badge(PRIORITY_BADGE[v.priority], v.priority) + '</div></div>'
      + '<div class="view-item"><div class="view-label">الحالة</div><div class="view-val">' + badge(STATUS_BADGE[v.status], v.status) + '</div></div>'
      + (v.works_done ? '<div class="view-item view-full"><div class="view-label">الأعمال المنفذة</div><div class="view-val">' + esc(v.works_done) + '</div></div>' : '')
      + (v.observations ? '<div class="view-item view-full"><div class="view-label">الملاحظات</div><div class="view-val">' + esc(v.observations) + '</div></div>' : '')
      + '</div>';
  }

  function renderFault(f) {
    return '<div class="view-grid">'
      + '<div class="view-section">بيانات العطل</div>'
      + '<div class="view-item"><div class="view-label">الكود</div><div class="view-val" style="font-family:var(--font-en)">' + esc(f.code) + '</div></div>'
      + '<div class="view-item"><div class="view-label">العميل</div><div class="view-val">' + esc(f.customer) + '</div></div>'
      + '<div class="view-item"><div class="view-label">المصعد</div><div class="view-val" style="font-family:var(--font-en)">' + esc(f.elevator) + '</div></div>'
      + '<div class="view-item"><div class="view-label">الفني</div><div class="view-val">' + esc(f.technician) + '</div></div>'
      + '<div class="view-item"><div class="view-label">نوع العطل</div><div class="view-val">' + esc(f.fault_type) + '</div></div>'
      + '<div class="view-item"><div class="view-label">الأولوية</div><div class="view-val">' + badge(PRIORITY_BADGE[f.priority], f.priority) + '</div></div>'
      + '<div class="view-item"><div class="view-label">تاريخ البلاغ</div><div class="view-val" style="direction:ltr">' + esc(f.reported_at) + '</div></div>'
      + '<div class="view-item"><div class="view-label">وقت الاستجابة</div><div class="view-val">' + esc(f.response_time) + '</div></div>'
      + '<div class="view-item"><div class="view-label">الحالة</div><div class="view-val">' + badge(STATUS_BADGE[f.status], f.status) + '</div></div>'
      + '<div class="view-item"><div class="view-label">الفوترة</div><div class="view-val">' + badge(f.billed ? 'badge-active' : 'badge-cancelled', f.billed ? 'مفوتر' : 'غير مفوتر') + '</div></div>'
      + (f.description ? '<div class="view-item view-full"><div class="view-label">الوصف</div><div class="view-val">' + esc(f.description) + '</div></div>' : '')
      + (f.resolution ? '<div class="view-item view-full"><div class="view-label">طريقة الحل</div><div class="view-val">' + esc(f.resolution) + '</div></div>' : '')
      + '</div>';
  }

  function renderPart(p) {
    var margin = p.sell_price > 0 ? ((p.profit / p.sell_price) * 100).toFixed(1) : 0;
    return '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:14px">'
      + '<div style="background:rgba(224,72,72,.08);border:1px solid rgba(224,72,72,.2);border-radius:8px;padding:12px;text-align:center">'
      + '<div style="font-size:11px;color:var(--text3)">التكلفة</div>'
      + '<div style="font-size:18px;font-weight:700;color:var(--danger);font-family:var(--font-en)">' + fmt(p.cost_price) + '</div></div>'
      + '<div style="background:rgba(42,127,255,.08);border:1px solid rgba(42,127,255,.2);border-radius:8px;padding:12px;text-align:center">'
      + '<div style="font-size:11px;color:var(--text3)">سعر البيع</div>'
      + '<div style="font-size:18px;font-weight:700;color:var(--accent);font-family:var(--font-en)">' + fmt(p.sell_price) + '</div></div>'
      + '<div style="background:rgba(31,184,122,.08);border:1px solid rgba(31,184,122,.2);border-radius:8px;padding:12px;text-align:center">'
      + '<div style="font-size:11px;color:var(--text3)">الربح (' + margin + '%)</div>'
      + '<div style="font-size:18px;font-weight:700;color:var(--success);font-family:var(--font-en)">' + fmt(p.profit) + '</div></div>'
      + '</div>'
      + '<div class="view-grid">'
      + '<div class="view-section">تفاصيل قطع الغيار</div>'
      + '<div class="view-item"><div class="view-label">الكود</div><div class="view-val" style="font-family:var(--font-en)">' + esc(p.code) + '</div></div>'
      + (p.visit_code ? '<div class="view-item"><div class="view-label">رقم الزيارة</div><div class="view-val" style="font-family:var(--font-en)">' + esc(p.visit_code) + '</div></div>' : '')
      + (p.fault_code ? '<div class="view-item"><div class="view-label">رقم العطل</div><div class="view-val" style="font-family:var(--font-en)">' + esc(p.fault_code) + '</div></div>' : '')
      + '<div class="view-item"><div class="view-label">العميل</div><div class="view-val">' + esc(p.customer) + '</div></div>'
      + '<div class="view-item"><div class="view-label">العقد</div><div class="view-val" style="font-family:var(--font-en)">' + esc(p.contract) + '</div></div>'
      + '<div class="view-item"><div class="view-label">المصعد</div><div class="view-val" style="font-family:var(--font-en)">' + esc(p.elevator) + '</div></div>'
      + '<div class="view-item"><div class="view-label">التاريخ</div><div class="view-val" style="direction:ltr">' + esc(p.billing_date) + '</div></div>'
      + '<div class="view-item"><div class="view-label">الفني</div><div class="view-val">' + esc(p.technician) + '</div></div>'
      + '<div class="view-item"><div class="view-label">طريقة الدفع</div><div class="view-val">' + esc(p.pay_method || '—') + '</div></div>'
      + '<div class="view-item"><div class="view-label">الحالة</div><div class="view-val">' + badge(STATUS_BADGE[p.status], p.status) + '</div></div>'
      + (p.description ? '<div class="view-item view-full"><div class="view-label">بيان القطع</div><div class="view-val">' + esc(p.description) + '</div></div>' : '')
      + '</div>';
  }

  function renderContract(c) {
    return '<div class="financial-summary" style="margin-bottom:14px">'
      + '<div class="fin-row"><span>قيمة العقد</span><span>' + fmt(c.value) + ' ر.س</span></div>'
      + '<div class="fin-row"><span>الضريبة (' + c.tax_pct + '%)</span><span>' + fmt(c.tax_amount) + ' ر.س</span></div>'
      + '<div class="fin-row"><span>الإجمالي</span><span>' + fmt(c.total) + ' ر.س</span></div>'
      + '</div>'
      + '<div class="view-grid">'
      + '<div class="view-section">بيانات العقد</div>'
      + '<div class="view-item"><div class="view-label">كود العقد</div><div class="view-val" style="font-family:var(--font-en)">' + esc(c.code) + '</div></div>'
      + '<div class="view-item"><div class="view-label">العميل</div><div class="view-val">' + esc(c.customer) + '</div></div>'
      + '<div class="view-item"><div class="view-label">نوع العقد</div><div class="view-val">' + esc(c.contract_type) + '</div></div>'
      + '<div class="view-item"><div class="view-label">المصاعد</div><div class="view-val" style="font-family:var(--font-en)">' + esc(c.elevators) + '</div></div>'
      + '<div class="view-item"><div class="view-label">حالة العقد</div><div class="view-val">' + badge(STATUS_BADGE[c.status], c.status) + '</div></div>'
      + '<div class="view-item"><div class="view-label">حالة الفاتورة</div><div class="view-val">' + badge(INV_BADGE[c.inv_status], c.inv_status) + '</div></div>'
      + '<div class="view-item"><div class="view-label">تاريخ البداية</div><div class="view-val" style="direction:ltr">' + esc(c.start_date) + '</div></div>'
      + '<div class="view-item"><div class="view-label">تاريخ الانتهاء</div><div class="view-val" style="direction:ltr">' + esc(c.end_date) + '</div></div>'
      + '<div class="view-item"><div class="view-label">مدة العقد</div><div class="view-val">' + (c.duration || '—') + ' شهر</div></div>'
      + '<div class="view-item"><div class="view-label">تكرار الصيانة</div><div class="view-val">' + esc(c.maint_freq || '—') + '</div></div>'
      + (c.notes ? '<div class="view-item view-full"><div class="view-label">ملاحظات</div><div class="view-val">' + esc(c.notes) + '</div></div>' : '')
      + '</div>';
  }

  var RENDERERS = {
    visit: function (d) { return renderVisit(d); },
    fault: function (d) { return renderFault(d); },
    part: function (d) { return renderPart(d); },
    contract: function (d) { return renderContract(d); },
  };

  var TITLES = {
    visit: function (d) { return d.code + ' — ' + d.customer; },
    fault: function (d) { return d.code + ' — ' + d.customer; },
    part: function (d) { return d.code + ' — قطع غيار'; },
    contract: function (d) { return d.code + ' — ' + d.customer; },
  };

  function open(type, id) {
    if (!API[type] || !id) return;
    ensureModal();
    openModal('جاري التحميل...', '<div class="cp-loading">⏳ جاري تحميل التفاصيل...</div>');
    fetch(API[type] + id)
      .then(function (r) {
        if (!r.ok) throw new Error('fetch failed');
        return r.json();
      })
      .then(function (data) {
        var titleFn = TITLES[type];
        var renderFn = RENDERERS[type];
        openModal(titleFn(data), renderFn(data));
      })
      .catch(function () {
        openModal('خطأ', '<div class="cp-empty">تعذر تحميل التفاصيل</div>');
      });
  }

  global.LiftCoreEntity = { open: open, close: close };
})(typeof window !== 'undefined' ? window : this);
