/**
 * LiftCore — عرض الأسماء والبنود + تطبيق EN على DOM بالكامل
 */
(function (global) {
  'use strict';

  var AR = /[\u0600-\u06FF]/;

  var ENUM = {
    'نشط': 'Active', 'نشطة': 'Active', 'غير نشط': 'Inactive',
    'متوقف': 'Stopped', 'متوقفة': 'Stopped',
    'تحت الصيانة': 'Under Maintenance', 'خارج الخدمة': 'Out of Service',
    'بدون عقد': 'No Contract', 'بدون مصاعد': 'No Elevators',
    'على وشك الانتهاء': 'Expiring Soon', 'منتهي': 'Expired', 'منتهية': 'Expired',
    'ملغي': 'Cancelled', 'معلق': 'Pending', 'محصّل': 'Collected', 'محصل': 'Collected',
    'غير محصل': 'Uncollected', 'مكتمل': 'Completed', 'مكتملة': 'Completed',
    'مفتوح': 'Open', 'مغلق': 'Closed', 'قيد التنفيذ': 'In Progress',
    'جاري التنفيذ': 'In Progress', 'جارية': 'In Progress', 'مُرسلة للفني': 'Sent to Technician',
    'عادية': 'Normal', 'عاجلة': 'Urgent', 'حرجة': 'Critical',
    'قابل للفوترة': 'Billable', 'ضمن العقد': 'Under Contract',
    'مدفوعة': 'Paid', 'غير مدفوعة': 'Unpaid', 'مدفوع جزئياً': 'Partially Paid',
    'متأخرة': 'Overdue', 'ملغاة': 'Cancelled',
    'صيانة دورية': 'Routine Maintenance', 'صيانة طارئة': 'Emergency Maintenance', 'صيانة': 'Maintenance',
    'مصعد ركاب': 'Passenger Elevator', 'مصعد بضائع': 'Freight Elevator',
    'مصعد مستشفى': 'Hospital Elevator', 'مصعد منزلي': 'Home Elevator',
    'مصعد بانوراما': 'Panoramic Elevator', 'مصعد خدمة': 'Service Elevator',
    'بغرفة آلة — MR': 'With Machine Room — MR', 'بدون غرفة — MRL': 'Machine Room Less — MRL',
    'هيدروليك — Hydraulic': 'Hydraulic',
    'مالك': 'Owner', 'مدير': 'Manager', 'مستأجر': 'Tenant', 'مسؤول': 'Contact',
    'عقد': 'Contract', 'عقد صيانة': 'Maintenance Contract', 'عقد تركيب': 'Installation Contract',
    'إيراد': 'Revenue', 'فاتورة': 'Invoice', 'عطل': 'Fault',
    'كجم': 'kg', 'ر.س': 'SAR', 'واتساب': 'WhatsApp',
    'نعم': 'Yes', 'لا': 'No', 'متاح': 'Available', 'مشغول': 'Busy', 'إجازة': 'On Leave',
    'مكة': 'Makkah', 'مكة المكرمة': 'Makkah', 'جدة': 'Jeddah', 'الرياض': 'Riyadh',
    'الدمام': 'Dammam', 'المدينة المنورة': 'Madinah', 'المدينة': 'Madinah', 'الطائف': 'Taif',
    'الشرائع': 'Al-Sharaie', 'الخضراء': 'Al-Khadra',
    'مصعد': 'Elevator', 'مصاعد': 'Elevators',
    'وارد': 'Incoming', 'صادر': 'Outgoing', 'منخفض': 'Low', 'نافد': 'Out of Service', 'كافي': 'Sufficient', 'قطعة': 'Piece',
  };

  var DOM_SKIP = 'script, style, input, select, textarea, .td-code, .td-actions, .lc-num, .lc-code, .lc-date, .lc-sar, [data-i18n-skip]';

  var DOM_TARGETS = [
    'table tbody td',
    '.badge',
    '.view-val', '.view-label', '.view-section',
    '.client-card-val', '.client-card-label', '.client-card-section',
    '.stat-mini-label', '.card-stat-label', '.card-section-title',
    '.form-section-title', '.modal-title',
    '.alert-expiry span', '.table-info', '.page-info',
    '.filter-select option', '.search-input',
    '.legend-item', '.alert-chip', '.tab', 'label', 'th',
  ].join(',');

  function currentLang() {
    if (global.__LC_LANG) return global.__LC_LANG;
    try {
      var ls = localStorage.getItem('liftcore_lang');
      if (ls) return ls;
    } catch (e) { /* ignore */ }
    return document.documentElement.getAttribute('lang') || 'ar';
  }

  function isEn() {
    return currentLang() === 'en';
  }

  function dict(key) {
    if (!key) return key;
    var k = String(key).replace(/\s+/g, ' ').trim();
    if (global.LiftCoreI18n && global.LiftCoreI18n.TEXT && global.LiftCoreI18n.TEXT[k]) {
      return global.LiftCoreI18n.TEXT[k];
    }
    if (global.__LC_TRANSLATIONS && global.__LC_TRANSLATIONS[k]) {
      return global.__LC_TRANSLATIONS[k];
    }
    if (ENUM[k]) return ENUM[k];
    return null;
  }

  function text(value) {
    if (value == null || value === '') return value;
    var s = String(value);
    if (!isEn()) return s;
    var exact = dict(s.trim());
    if (exact) return exact;
    if (AR.test(s) && global.LiftCoreTranslit) {
      return global.LiftCoreTranslit.arabicToLatin(s);
    }
    return s.replace(/(\d+)\s*كجم/g, '$1 kg').replace(/ر\.س/g, 'SAR');
  }

  function name(arName, enName) {
    if (!isEn()) return arName || '';
    if (enName && String(enName).trim()) return String(enName).trim();
    return text(arName || '');
  }

  function clientName(c) {
    if (!c) return '';
    return name(c.name, c.name_en);
  }

  function rowCustomer(row) {
    if (!row) return '';
    return name(row.customer, row.customer_name_en);
  }

  function techName(t) {
    if (!t) return '';
    if (typeof t === 'string') return text(t);
    return name(t.name, t.name_en);
  }

  function fmtEnCount(n, singular, plural) {
    n = Number(n) || 0;
    return n + ' ' + (n === 1 ? singular : plural);
  }

  function fmtMoney(n) {
    var v = Number(n) || 0;
    if (isEn()) return v.toLocaleString('en-US', { maximumFractionDigits: 2 }) + ' SAR';
    return v.toLocaleString('ar-SA', { maximumFractionDigits: 2 }) + ' \u0631.\u0633';
  }

  function fmtClientsCount(n) { n = Number(n) || 0; return isEn() ? fmtEnCount(n, 'client', 'clients') : n + ' \u0639\u0645\u064A\u0644'; }
  function fmtElevatorsCount(n) { n = Number(n) || 0; return isEn() ? fmtEnCount(n, 'elevator', 'elevators') : n + ' \u0645\u0635\u0639\u062F'; }
  function fmtContractsCount(n) { n = Number(n) || 0; return isEn() ? fmtEnCount(n, 'contract', 'contracts') : n + ' \u0639\u0642\u062F'; }
  function fmtFaultsCount(n) { n = Number(n) || 0; return isEn() ? fmtEnCount(n, 'fault', 'faults') : n + ' \u0639\u0637\u0644'; }
  function fmtVisitsCount(n) { n = Number(n) || 0; return isEn() ? fmtEnCount(n, 'visit', 'visits') : n + ' \u0632\u064A\u0627\u0631\u0629'; }
  function fmtTechniciansCount(n) { n = Number(n) || 0; return isEn() ? fmtEnCount(n, 'technician', 'technicians') : n + ' \u0641\u0646\u064A'; }
  function fmtRecordsCount(n) { n = Number(n) || 0; return isEn() ? fmtEnCount(n, 'record', 'records') : n + ' \u0633\u062C\u0644'; }
  function fmtItemsCount(n) { n = Number(n) || 0; return isEn() ? fmtEnCount(n, 'item', 'items') : n + ' \u0635\u0646\u0641'; }
  function fmtMovementsCount(n) { n = Number(n) || 0; return isEn() ? fmtEnCount(n, 'movement', 'movements') : n + ' \u062D\u0631\u0643\u0629'; }
  function fmtInvoicesCount(n) { n = Number(n) || 0; return isEn() ? fmtEnCount(n, 'invoice', 'invoices') : n + ' \u0641\u0627\u062A\u0648\u0631\u0629'; }
  function fmtShowing(a, b) { return isEn() ? ('Showing ' + a + ' of ' + b) : ('\u0639\u0631\u0636 ' + a + ' \u0645\u0646 ' + b); }

  function setCountEl(id, textVal) {
    var el = document.getElementById(id);
    if (el) el.textContent = textVal;
  }

  function shouldSkipEl(el) {
    if (!el || el.closest('[data-i18n-skip]')) return true;
    if (el.matches && el.matches(DOM_SKIP)) return true;
    if (el.closest && el.closest(DOM_SKIP)) return true;
    if (el.querySelector && el.querySelector('svg, img, input, select, button, .td-actions')) return true;
    return false;
  }

  function applyElText(el, lang) {
    if (shouldSkipEl(el)) return;
    if (el.tagName === 'INPUT' && el.placeholder) {
      if (lang === 'en') {
        if (!el.dataset.lcPhAr) el.dataset.lcPhAr = el.placeholder;
        var ph = text(el.placeholder);
        if (ph !== el.placeholder) el.placeholder = ph;
      } else if (el.dataset.lcPhAr) {
        el.placeholder = el.dataset.lcPhAr;
      }
      return;
    }
    var raw = el.textContent;
    if (!raw || !String(raw).trim()) return;
    if (lang === 'en') {
      if (el.dataset.lcAr == null) el.dataset.lcAr = raw;
      var en = text(raw);
      if (en !== raw) el.textContent = en;
    } else if (el.dataset.lcAr != null) {
      el.textContent = el.dataset.lcAr;
    }
  }

  /** تطبيق EN/AR على جداول وبادجات وعناوين — كل الصفحات */
  function applyDom(root, lang) {
    root = root || document;
    lang = lang || currentLang();
    root.querySelectorAll(DOM_TARGETS).forEach(function (el) {
      applyElText(el, lang);
    });
    root.querySelectorAll('.search-input').forEach(function (el) {
      applyElText(el, lang);
    });
  }

  function refreshPage() {
    if (typeof global.__lcRefreshPage === 'function') global.__lcRefreshPage();
    applyDom(document, currentLang());
  }

  function onLangChange(lang) {
    global.__LC_LANG = lang;
    refreshPage();
  }

  document.addEventListener('liftcore:lang', function (ev) {
    onLangChange((ev.detail && ev.detail.lang) || currentLang());
  });

  document.addEventListener('liftcore:display-refresh', function () {
    applyDom(document, currentLang());
  });

  function lockGlobalSetLang() {
    if (global.LiftCoreI18n && global.LiftCoreI18n.setLang) {
      global.setLang = global.LiftCoreI18n.setLang;
    }
  }

  [0, 100, 400, 1000, 2500].forEach(function (ms) { setTimeout(lockGlobalSetLang, ms); });
  global.addEventListener('load', lockGlobalSetLang);

  global.lcDisp = text;
  global.lcName = name;

  global.LiftCoreDisplay = {
    isEn: isEn,
    currentLang: currentLang,
    text: text,
    name: name,
    clientName: clientName,
    rowCustomer: rowCustomer,
    techName: techName,
    fmtMoney: fmtMoney,
    fmtClientsCount: fmtClientsCount,
    fmtElevatorsCount: fmtElevatorsCount,
    fmtContractsCount: fmtContractsCount,
    fmtFaultsCount: fmtFaultsCount,
    fmtVisitsCount: fmtVisitsCount,
    fmtTechniciansCount: fmtTechniciansCount,
    fmtRecordsCount: fmtRecordsCount,
    fmtItemsCount: fmtItemsCount,
    fmtMovementsCount: fmtMovementsCount,
    fmtInvoicesCount: fmtInvoicesCount,
    fmtShowing: fmtShowing,
    setCountEl: setCountEl,
    applyDom: applyDom,
    refreshPage: refreshPage,
    ENUM: ENUM,
  };
})(window);
