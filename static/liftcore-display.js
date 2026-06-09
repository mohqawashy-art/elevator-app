/**

 * LiftCore — عرض الأسماء والبنود حسب اللغة (عربي / EN)

 */

(function (global) {

  'use strict';



  var AR = /[\u0600-\u06FF]/;



  var ENUM = {

    'نشط': 'Active',

    'نشطة': 'Active',

    'غير نشط': 'Inactive',

    'متوقف': 'Stopped',

    'متوقفة': 'Stopped',

    'تحت الصيانة': 'Under Maintenance',

    'خارج الخدمة': 'Out of Service',

    'بدون عقد': 'No Contract',

    'بدون مصاعد': 'No Elevators',

    'على وشك الانتهاء': 'Expiring Soon',

    'منتهي': 'Expired',

    'منتهية': 'Expired',

    'ملغي': 'Cancelled',

    'معلق': 'Pending',

    'محصّل': 'Collected',

    'محصل': 'Collected',

    'غير محصل': 'Uncollected',

    'مكتمل': 'Completed',

    'مكتملة': 'Completed',

    'مفتوح': 'Open',

    'مغلق': 'Closed',

    'قيد التنفيذ': 'In Progress',

    'جاري التنفيذ': 'In Progress',

    'جارية': 'In Progress',

    'مُرسلة للفني': 'Sent to Technician',

    'عادية': 'Normal',

    'عاجلة': 'Urgent',

    'حرجة': 'Critical',

    'قابل للفوترة': 'Billable',

    'ضمن العقد': 'Under Contract',

    'مدفوعة': 'Paid',

    'غير مدفوعة': 'Unpaid',

    'مدفوع جزئياً': 'Partially Paid',

    'متأخرة': 'Overdue',

    'ملغاة': 'Cancelled',

    'فاتورة ضريبية': 'Tax Invoice',

    'فاتورة ضريبية مبسطة': 'Simplified Tax Invoice',

    'سند قبض': 'Receipt Voucher',

    'إشعار دائن': 'Credit Note',

    'صيانة دورية': 'Routine Maintenance',

    'صيانة طارئة': 'Emergency Maintenance',

    'صيانة': 'Maintenance',

    'مصعد ركاب': 'Passenger Elevator',

    'مصعد بضائع': 'Freight Elevator',

    'مصعد مستشفى': 'Hospital Elevator',

    'مصعد منزلي': 'Home Elevator',

    'مصعد بانوراما': 'Panoramic Elevator',

    'مصعد خدمة': 'Service Elevator',

    'بغرفة آلة — MR': 'With Machine Room — MR',

    'بدون غرفة — MRL': 'Machine Room Less — MRL',

    'هيدروليك — Hydraulic': 'Hydraulic',

    'مالك': 'Owner',

    'مدير': 'Manager',

    'مستأجر': 'Tenant',

    'مسؤول': 'Contact',

    'عقد': 'Contract',

    'عقد صيانة': 'Maintenance Contract',

    'عقد تركيب': 'Installation Contract',

    'إيراد': 'Revenue',

    'فاتورة': 'Invoice',

    'عطل': 'Fault',

    'كجم': 'kg',

    'ر.س': 'SAR',

    'واتساب': 'WhatsApp',

    'واتساب المسؤول': 'Contact WhatsApp',

    'تواصل واتساب': 'WhatsApp',

    'نعم': 'Yes',

    'لا': 'No',

    'متاح': 'Available',

    'مشغول': 'Busy',

    'إجازة': 'On Leave',

    'مكة': 'Makkah',

    'مكة المكرمة': 'Makkah',

    'جدة': 'Jeddah',

    'الرياض': 'Riyadh',

    'الدمام': 'Dammam',

    'المدينة المنورة': 'Madinah',

    'المدينة': 'Madinah',

    'الطائف': 'Taif',

    'الشرائع': 'Al-Sharaie',

    'الخضراء': 'Al-Khadra',

    'مصعد': 'Elevator',

    'مصاعد': 'Elevators',

    'وارد': 'Incoming',

    'صادر': 'Outgoing',

    'منخفض': 'Low',

    'نافد': 'Out of Stock',

    'كافي': 'Sufficient',

    'قطعة': 'Piece',

  };



  function isEn() {

    var lang = global.__LC_LANG;

    if (!lang) {

      try { lang = localStorage.getItem('liftcore_lang'); } catch (e) { lang = null; }

    }

    return lang === 'en';

  }



  function dict(key) {

    if (!key) return key;

    var k = String(key).replace(/\s+/g, ' ').trim();

    if (global.LiftCoreI18n && global.LiftCoreI18n.TEXT && global.LiftCoreI18n.TEXT[k]) {

      return global.LiftCoreI18n.TEXT[k];

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

    if (isEn()) {

      return v.toLocaleString('en-US', { maximumFractionDigits: 2 }) + ' SAR';

    }

    return v.toLocaleString('ar-SA', { maximumFractionDigits: 2 }) + ' \u0631.\u0633';

  }



  function fmtClientsCount(n) {

    n = Number(n) || 0;

    if (isEn()) return fmtEnCount(n, 'client', 'clients');

    return n + ' \u0639\u0645\u064A\u0644';

  }



  function fmtElevatorsCount(n) {

    n = Number(n) || 0;

    if (isEn()) return fmtEnCount(n, 'elevator', 'elevators');

    return n + ' \u0645\u0635\u0639\u062F';

  }



  function fmtContractsCount(n) {

    n = Number(n) || 0;

    if (isEn()) return fmtEnCount(n, 'contract', 'contracts');

    return n + ' \u0639\u0642\u062F';

  }



  function fmtFaultsCount(n) {

    n = Number(n) || 0;

    if (isEn()) return fmtEnCount(n, 'fault', 'faults');

    return n + ' \u0639\u0637\u0644';

  }



  function fmtVisitsCount(n) {

    n = Number(n) || 0;

    if (isEn()) return fmtEnCount(n, 'visit', 'visits');

    return n + ' \u0632\u064A\u0627\u0631\u0629';

  }



  function fmtTechniciansCount(n) {

    n = Number(n) || 0;

    if (isEn()) return fmtEnCount(n, 'technician', 'technicians');

    return n + ' \u0641\u0646\u064A';

  }



  function fmtRecordsCount(n) {

    n = Number(n) || 0;

    if (isEn()) return fmtEnCount(n, 'record', 'records');

    return n + ' \u0633\u062C\u0644';

  }



  function fmtItemsCount(n) {

    n = Number(n) || 0;

    if (isEn()) return fmtEnCount(n, 'item', 'items');

    return n + ' \u0635\u0646\u0641';

  }



  function fmtMovementsCount(n) {

    n = Number(n) || 0;

    if (isEn()) return fmtEnCount(n, 'movement', 'movements');

    return n + ' \u062D\u0631\u0643\u0629';

  }



  function fmtInvoicesCount(n) {

    n = Number(n) || 0;

    if (isEn()) return fmtEnCount(n, 'invoice', 'invoices');

    return n + ' \u0641\u0627\u062A\u0648\u0631\u0629';

  }



  function fmtShowing(a, b) {

    if (isEn()) return 'Showing ' + a + ' of ' + b;

    return '\u0639\u0631\u0636 ' + a + ' \u0645\u0646 ' + b;

  }



  function setCountEl(id, textVal) {

    var el = document.getElementById(id);

    if (el) el.textContent = textVal;

  }



  function refreshPage() {

    document.dispatchEvent(new CustomEvent('liftcore:display-refresh'));

    if (typeof global.__lcRefreshPage === 'function') global.__lcRefreshPage();

  }



  function applyToPage(lang) {

    lang = lang || (isEn() ? 'en' : 'ar');

    if (global.LiftCoreI18n) global.LiftCoreI18n.apply(lang);

    refreshPage();

  }



  document.addEventListener('liftcore:lang', function (ev) {

    var lang = ev.detail && ev.detail.lang;

    if (!lang) return;

    applyToPage(lang);

  });



  document.addEventListener('liftcore:display-refresh', function () {

    if (typeof global.__lcRefreshPage === 'function') global.__lcRefreshPage();

  });



  global.lcDisp = text;

  global.lcName = name;



  global.LiftCoreDisplay = {

    isEn: isEn,

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

    applyToPage: applyToPage,

    refreshPage: refreshPage,

    ENUM: ENUM,

  };

})(window);


