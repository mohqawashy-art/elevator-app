/**
 * LiftCore — تصدير CSV لكل الحقول المسجّلة في كائنات الصفحة
 */
(function (global) {
  'use strict';

  function cellValue(v) {
    if (v == null) return '';
    if (typeof v === 'boolean') return v ? 'نعم' : 'لا';
    if (Array.isArray(v)) {
      if (!v.length) return '';
      return v.map(function (item) {
        if (item == null) return '';
        if (typeof item === 'object') {
          if (item.label && (item.number || item.phone)) {
            return item.label + ': ' + (item.number || item.phone);
          }
          if (item.name) return item.name;
          if (item.title) return item.title;
          if (item.doc_type || item.file_name) {
            return [item.doc_type, item.title || item.file_name].filter(Boolean).join(' — ');
          }
          try { return JSON.stringify(item); } catch (e) { return String(item); }
        }
        return String(item);
      }).filter(Boolean).join(' | ');
    }
    if (typeof v === 'object') {
      try { return JSON.stringify(v); } catch (e) { return String(v); }
    }
    return String(v);
  }

  function escapeCsv(v) {
    return '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"';
  }

  function download(filename, matrix) {
    var csv = matrix.map(function (r) {
      return r.map(escapeCsv).join(',');
    }).join('\n');
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' }));
    a.download = filename || 'export.csv';
    a.click();
  }

  function datedName(base) {
    return base + '_' + new Date().toISOString().split('T')[0] + '.csv';
  }

  /**
   * @param {object[]} data
   * @param {{filename?:string,labels?:object,skip?:object|string[],transforms?:object,extraColumns?:array,includeId?:boolean}} opts
   */
  function exportRecords(data, opts) {
    opts = opts || {};
    data = Array.isArray(data) ? data : [];
    var labels = opts.labels || {};
    var transforms = opts.transforms || {};
    var skip = {};
    var skipIn = opts.skip;
    if (Array.isArray(skipIn)) skipIn.forEach(function (k) { skip[k] = true; });
    else if (skipIn && typeof skipIn === 'object') {
      Object.keys(skipIn).forEach(function (k) { if (skipIn[k]) skip[k] = true; });
    }
    if (!('id' in skip) && opts.includeId !== true) skip.id = true;

    var seen = {};
    var keys = [];
    Object.keys(labels).forEach(function (k) {
      if (skip[k] || seen[k]) return;
      seen[k] = true;
      keys.push(k);
    });
    data.forEach(function (row) {
      if (!row || typeof row !== 'object') return;
      Object.keys(row).forEach(function (k) {
        if (skip[k] || seen[k]) return;
        seen[k] = true;
        keys.push(k);
      });
    });

    var headers = keys.map(function (k) { return labels[k] || k; });
    var extras = opts.extraColumns || [];
    extras.forEach(function (col) { headers.push(col.label || col.key || ''); });

    var matrix = [headers];
    data.forEach(function (row) {
      var line = keys.map(function (k) {
        var raw = row ? row[k] : '';
        if (transforms[k]) {
          try { raw = transforms[k](raw, row); } catch (e) { /* keep */ }
        }
        return cellValue(raw);
      });
      extras.forEach(function (col) {
        try { line.push(cellValue(col.value ? col.value(row) : '')); }
        catch (e) { line.push(''); }
      });
      matrix.push(line);
    });
    download(opts.filename || datedName('export'), matrix);
  }

  var SKIP_COMMON = {
    id: 1,
    customer_id: 1,
    contract_id: 1,
    elevator_id: 1,
    tech_id: 1,
    tech_ids: 1,
    item_id: 1,
    fault_id: 1,
    parent_invoice_id: 1,
    revenue_id: 1,
    docs: 1,
    technicians: 1,
    wa: 1
  };

  var LABELS = {
    client: {
      code: 'الكود', name: 'الاسم', name_en: 'الاسم الإنجليزي', entity_type: 'نوع المتعاقد',
      city: 'المدينة', district: 'الحي', address: 'العنوان', national_address: 'العنوان الوطني',
      phone: 'الهاتف', phone2: 'واتساب / هاتف 2', extra_phones: 'أرقام إضافية', email: 'البريد الإلكتروني',
      contact: 'المسؤول', role: 'صفة المسؤول',
      national_id: 'هوية المتعاقد', cr_number: 'السجل التجاري', vat_number: 'الرقم الضريبي',
      elevators: 'عدد المصاعد', fleet_status: 'حالة الأسطول', contracts: 'عدد العقود',
      contract_status: 'حالة العقد', status: 'حالة العميل',
      lat: 'خط العرض', lng: 'خط الطول', maps_url: 'رابط الخريطة', building_photo_url: 'رابط صورة المبنى',
      notes: 'ملاحظات'
    },
    elevator: {
      code: 'الكود', customer: 'العميل', customer_name_en: 'اسم العميل إنجليزي',
      building: 'المبنى', city: 'المدينة', district: 'الحي', address: 'العنوان',
      elev_type: 'نوع المصعد', brand: 'الماركة', model: 'الموديل',
      capacity: 'الحمولة كجم', capacity_persons: 'عدد الأشخاص', floors: 'الطوابق', stops: 'التوقفات',
      doors: 'عدد الأبواب', speed: 'السرعة', serial: 'الرقم التسلسلي',
      machine_type: 'نوع الآلة', door_type: 'نوع الباب',
      control_type: 'نوع التحكم', control_drive: 'نظام الدفع', control_operation: 'نمط التشغيل', control_detail: 'تفاصيل التحكم',
      install_date: 'تاريخ التركيب', warranty_end: 'انتهاء الضمان',
      last_maint: 'آخر صيانة', next_maint: 'الصيانة القادمة', maint_freq: 'تكرار الصيانة',
      status: 'الحالة', notes: 'ملاحظات',
      customer_lat: 'خط عرض العميل', customer_lng: 'خط طول العميل', customer_status: 'حالة العميل'
    },
    contract: {
      code: 'الكود', customer: 'العميل', customer_name_en: 'اسم العميل إنجليزي', buildings: 'المباني',
      customer_city: 'مدينة العميل', customer_district: 'حي العميل',
      contract_type: 'نوع العقد', start_date: 'البداية', end_date: 'الانتهاء', duration: 'المدة بالأشهر',
      elevators: 'عدد المصاعد', elevator_ids: 'معرفات المصاعد',
      maint_freq: 'تكرار الصيانة', visits_month: 'زيارات شهرياً',
      value: 'القيمة', tax_pct: 'نسبة الضريبة', tax_amount: 'مبلغ الضريبة', total: 'الإجمالي',
      pay_terms: 'شروط الدفع', paid_amount: 'المبلغ المسدد', inv_status: 'حالة الفاتورة',
      status: 'حالة العقد', display_status: 'حالة العرض', renewed: 'تم تجديده',
      reminder_date: 'تاريخ التذكير', due_date: 'تاريخ الاستحقاق',
      city: 'المدينة', district: 'الحي', address: 'العنوان', notes: 'ملاحظات',
      file_url: 'رابط الملف', file_name: 'اسم الملف',
      customer_lat: 'خط عرض العميل', customer_lng: 'خط طول العميل', customer_status: 'حالة العميل'
    },
    technician: {
      code: 'الكود', name: 'الاسم', name_en: 'الاسم الإنجليزي',
      phone: 'الهاتف', phone2: 'واتساب', email: 'البريد',
      job_title: 'المسمى', specialization: 'التخصص', team: 'البوابة', city: 'المدينة',
      nationality: 'الجنسية', experience_years: 'سنوات الخبرة',
      national_id: 'رقم الهوية', national_id_expiry: 'انتهاء الهوية',
      license_number: 'رقم الرخصة', license_expiry: 'انتهاء الرخصة',
      districts: 'الأحياء', hire_date: 'تاريخ التعيين', salary: 'الراتب',
      emergency: 'طوارئ', status: 'الحالة', display_status: 'حالة العرض',
      visits: 'الزيارات', faults: 'الأعطال', notes: 'ملاحظات',
      photo_url: 'رابط الصورة', signature_url: 'رابط التوقيع',
      has_sign_pin: 'لديه PIN', documents: 'عدد المستندات'
    },
    visit: {
      code: 'الكود', customer: 'العميل', customer_name_en: 'اسم العميل إنجليزي',
      elevator: 'المصعد', building: 'المبنى', technician: 'الفني',
      visit_type: 'نوع الزيارة', visit_date: 'التاريخ', plan_month: 'شهر الخطة',
      visit_time: 'الوقت', priority: 'الأولوية', status: 'الحالة',
      completed_at: 'تاريخ الإكمال', works_done: 'الأعمال المنجزة',
      observations: 'الملاحظات الفنية', notes: 'ملاحظات',
      fault_code: 'كود العطل المرتبط',
      has_report: 'يوجد تقرير', report_filled: 'بنود مكتملة', report_total: 'إجمالي البنود',
      report_all_ok: 'كل البنود سليمة', report_flagged_items: 'بنود معلّمة'
    },
    fault: {
      code: 'الكود', customer: 'العميل', customer_name_en: 'اسم العميل إنجليزي',
      elevator: 'المصعد', technician: 'الفني',
      fault_type: 'نوع العطل', description: 'الوصف', client_report: 'بلاغ العميل',
      priority: 'الأولوية', reported_at: 'تاريخ البلاغ', reported_at_local: 'وقت البلاغ',
      response_time: 'زمن الاستجابة', status: 'الحالة', resolution: 'الحل',
      billed: 'مفوتر', visit_code: 'كود الزيارة', notes: 'ملاحظات',
      reporter_name: 'اسم المبلّغ', reporter_phone: 'هاتف المبلّغ',
      needs_parts: 'يحتاج قطع', parts_lines: 'قطع الغيار', has_report: 'يوجد تقرير'
    },
    revenue: {
      code: 'الكود', customer: 'العميل', contract: 'العقد',
      revenue_date: 'التاريخ', revenue_type: 'النوع', pay_method: 'طريقة الدفع',
      amount: 'المبلغ', tax_amount: 'الضريبة', total: 'الإجمالي', status: 'الحالة',
      reference: 'المرجع', proof_url: 'رابط الإثبات', has_proof: 'يوجد إثبات',
      notes: 'ملاحظات', created_by: 'سجّله'
    },
    expense: {
      code: 'الكود', expense_date: 'التاريخ', expense_type: 'النوع', description: 'الوصف',
      responsible: 'المسؤول', pay_method: 'طريقة الدفع', amount: 'المبلغ',
      reference: 'المرجع', proof_url: 'رابط الإثبات', has_proof: 'يوجد إثبات',
      notes: 'ملاحظات', created_by: 'سجّله'
    },
    invoice: {
      code: 'الكود', invoice_type: 'النوع', customer: 'العميل', customer_name_en: 'اسم العميل إنجليزي',
      contract: 'العقد', invoice_date: 'التاريخ', due_date: 'الاستحقاق', description: 'البيان',
      amount: 'المبلغ', tax_amount: 'الضريبة', total: 'الإجمالي',
      pay_method: 'طريقة الدفع', status: 'الحالة', notes: 'ملاحظات',
      is_receipt: 'سند قبض', customer_whatsapp: 'واتساب العميل', customer_contact: 'مسؤول العميل'
    },
    inventory: {
      code: 'الكود', name: 'الاسم', category: 'التصنيف', unit: 'الوحدة',
      current_qty: 'الرصيد', min_qty: 'الحد الأدنى',
      buy_price: 'سعر الشراء', sell_price: 'سعر البيع', stock_value: 'قيمة المخزون',
      order_status: 'حالة الطلب', supplier: 'المورد', location: 'الموقع', notes: 'ملاحظات'
    },
    parts: {
      code: 'الكود', customer: 'العميل', customer_name_en: 'اسم العميل إنجليزي',
      contract: 'العقد', elevator: 'المصعد', technician: 'الفني',
      billing_date: 'التاريخ', description: 'البيان',
      cost_price: 'التكلفة', sell_price: 'سعر البيع', profit: 'الربح',
      payment_note: 'بيان السداد', status: 'الحالة',
      visit_code: 'كود الزيارة', fault_code: 'كود العطل',
      notes: 'ملاحظات', parts_lines: 'تفاصيل القطع'
    },
    stock: {
      code: 'الكود', movement_date: 'التاريخ', direction: 'الاتجاه', movement_type: 'النوع',
      item_code: 'كود الصنف', item_name: 'الصنف', quantity: 'الكمية',
      unit_price: 'سعر الوحدة', total_value: 'القيمة', technician: 'الفني',
      reason: 'السبب', notes: 'ملاحظات'
    }
  };

  global.LiftCoreCsv = {
    cellValue: cellValue,
    escapeCsv: escapeCsv,
    download: download,
    datedName: datedName,
    exportRecords: exportRecords,
    SKIP_COMMON: SKIP_COMMON,
    LABELS: LABELS
  };
})(typeof window !== 'undefined' ? window : this);
