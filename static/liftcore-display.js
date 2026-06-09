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
    'إيراد': 'Revenue',
    'فاتورة': 'Invoice',
    'صيانة': 'Maintenance',
    'عطل': 'Fault',
    'كجم': 'kg',
    'ر.س': 'SAR',
    'واتساب': 'WhatsApp',
    'واتساب المسؤول': 'Contact WhatsApp',
    'تواصل واتساب': 'WhatsApp',
    'مكة': 'Makkah',
    'مكة المكرمة': 'Makkah',
    'جدة': 'Jeddah',
    'الرياض': 'Riyadh',
    'الدمام': 'Dammam',
    'المدينة المنورة': 'Madinah',
    'المدينة': 'Madinah',
    'الشرائع': 'Al-Sharaie',
    'الخضراء': 'Al-Khadra',
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

  function fmtMoney(n) {
    var v = Number(n) || 0;
    if (isEn()) {
      return v.toLocaleString('en-US', { maximumFractionDigits: 2 }) + ' SAR';
    }
    return v.toLocaleString('ar-SA', { maximumFractionDigits: 2 }) + ' \u0631.\u0633';
  }

  function fmtClientsCount(n) {
    n = Number(n) || 0;
    if (isEn()) return n + (n === 1 ? ' client' : ' clients');
    return n + ' \u0639\u0645\u064A\u0644';
  }

  function fmtElevatorsCount(n) {
    n = Number(n) || 0;
    if (isEn()) return n + (n === 1 ? ' elevator' : ' elevators');
    return n + ' \u0645\u0635\u0639\u062F';
  }

  function fmtShowing(a, b) {
    if (isEn()) return 'Showing ' + a + ' of ' + b;
    return '\u0639\u0631\u0636 ' + a + ' \u0645\u0646 ' + b;
  }

  function applyToPage() {
    if (!isEn()) return;
    if (global.LiftCoreI18n) global.LiftCoreI18n.apply('en');
    document.dispatchEvent(new CustomEvent('liftcore:display-refresh'));
  }

  document.addEventListener('liftcore:lang', function (ev) {
    if (ev.detail && ev.detail.lang === 'en') applyToPage();
  });

  global.LiftCoreDisplay = {
    isEn: isEn,
    text: text,
    name: name,
    clientName: clientName,
    fmtMoney: fmtMoney,
    fmtClientsCount: fmtClientsCount,
    fmtElevatorsCount: fmtElevatorsCount,
    fmtShowing: fmtShowing,
    applyToPage: applyToPage,
    ENUM: ENUM,
  };
})(window);
