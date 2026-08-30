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
    'نصف أوتوماتيك': 'Semi-Automatic', 'نصف اتوماتيك': 'Semi-Automatic',
    'أوتوماتيك': 'Automatic', 'اتوماتيك': 'Automatic',
    'سنتر أوتوماتيك': 'Center Automatic', 'تلسكوبي': 'Telescopic',
    'مصعد ركاب': 'Passenger Elevator', 'مصعد بضائع': 'Freight Elevator',
    'مصعد مستشفى': 'Hospital Elevator', 'مصعد منزلي': 'Home Elevator',
    'مصعد بانوراما': 'Panoramic Elevator', 'مصعد خدمة': 'Service Elevator',
    'بغرفة آلة — MR': 'With Machine Room — MR', 'بدون غرفة — MRL': 'Machine Room Less — MRL',
    'هيدروليك — Hydraulic': 'Hydraulic',
    'مالك': 'Owner', 'مدير': 'Manager', 'وكيل': 'Agent', 'حارس': 'Guard', 'مشرف': 'Supervisor',
    'مستأجر': 'Tenant', 'مسؤول': 'Contact',
    'عقد': 'Contract', 'عقد صيانة': 'Maintenance Contract', 'عقد تركيب': 'Installation Contract', 'عقد تحديث': 'Modernization Contract',
    'إيراد': 'Revenue', 'فاتورة': 'Invoice', 'عطل': 'Fault',
    'كجم': 'kg', 'ر.س': '\u20C1', 'واتساب': 'WhatsApp',
    'نعم': 'Yes', 'لا': 'No', 'متاح': 'Available', 'مشغول': 'Busy', 'إجازة': 'On Leave',
    'مكة': 'Makkah', 'مكة المكرمة': 'Makkah', 'جدة': 'Jeddah', 'الرياض': 'Riyadh',
    'الدمام': 'Dammam', 'المدينة المنورة': 'Madinah', 'المدينة': 'Madinah', 'الطائف': 'Taif',
    'الشرائع': 'Al-Sharaie', 'الخضراء': 'Al-Khadra',
    'مصعد': 'Elevator', 'مصاعد': 'Elevators',
    'وارد': 'Incoming', 'صادر': 'Outgoing', 'منخفض': 'Low', 'نافد': 'Out of Service', 'كافي': 'Sufficient', 'قطعة': 'Piece',
  };

  var DOM_SKIP = 'script, style, input, select, textarea, .td-code, .td-actions, .lc-num, .lc-code, .lc-date, .lc-sar, .lc-sar-char, [data-i18n-skip]';

  var DOM_TARGETS = [
    'table tbody td',
    '.badge',
    '.view-val', '.view-label', '.view-section',
    '.client-card-val', '.client-card-label', '.client-card-section',
    '.stat-mini-label', '.card-stat-label', '.card-section-title',
    '.form-section-title', '.modal-title',
    '.alert-expiry span', '.table-info', '.page-info',
    '.filter-select option',
    '.legend-item', '.alert-chip', '.tab', 'label', 'th',
  ].join(',');

  function applySearchPlaceholders(root, lang) {
    (root || document).querySelectorAll('.search-input[placeholder]').forEach(function (el) {
      if (el.closest('.modal-overlay:not(.open)')) return;
      if (lang === 'en') {
        if (!el.dataset.lcPhAr && AR.test(el.placeholder)) el.dataset.lcPhAr = el.placeholder;
        var ph = text(el.placeholder);
        if (ph !== el.placeholder) el.placeholder = ph;
      } else if (el.dataset.lcPhAr) {
        el.placeholder = el.dataset.lcPhAr;
        delete el.dataset.lcPhAr;
      }
    });
  }

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
    return s.replace(/(\d+)\s*كجم/g, '$1 kg').replace(/ر\.س/g, '\u20C1');
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
    /* رمز الريال السعودي الجديد U+20C1 في اللغتين */
    return v.toLocaleString('en-US', { maximumFractionDigits: 2 }) + ' \u20C1';
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
  function fmtTransactionsCount(n) { n = Number(n) || 0; return isEn() ? fmtEnCount(n, 'transaction', 'transactions') : n + ' \u0639\u0645\u0644\u064A\u0629'; }
  function fmtMargin(p) { return isEn() ? ('Margin ' + p + '%') : ('\u0647\u0627\u0645\u0634 ' + p + '%'); }
  function fmtShowing(a, b) { return isEn() ? ('Showing ' + a + ' of ' + b) : ('\u0639\u0631\u0636 ' + a + ' \u0645\u0646 ' + b); }
  function fmtPageRange(start, end, filtered, master) {
    master = master != null ? master : filtered;
    if (!filtered) {
      return isEn() ? ('Showing 0 of ' + master) : ('\u0639\u0631\u0636 0 \u0645\u0646 ' + master);
    }
    if (start === end) {
      return isEn()
        ? ('Showing ' + start + ' of ' + master + (filtered !== master ? ' (' + filtered + ' filtered)' : ''))
        : ('\u0639\u0631\u0636 ' + start + ' \u0645\u0646 ' + master + (filtered !== master ? ' (\u0645\u0639\u0631\u0651\u064E\u0627\u0629 ' + filtered + ')' : ''));
    }
    return isEn()
      ? ('Showing ' + start + '\u2013' + end + ' of ' + master + (filtered !== master ? ' (' + filtered + ' filtered)' : ''))
      : ('\u0639\u0631\u0636 ' + start + '\u2013' + end + ' \u0645\u0646 ' + master + (filtered !== master ? ' (\u0645\u0639\u0631\u0651\u064E\u0627\u0629 ' + filtered + ')' : ''));
  }

  function setCountEl(id, textVal) {
    var el = document.getElementById(id);
    if (el) el.textContent = textVal;
  }

  function shouldSkipEl(el) {
    if (!el || el.closest('[data-i18n-skip]')) return true;
    if (el.hasAttribute('data-lc-t') || el.hasAttribute('data-lc-ph') || el.hasAttribute('data-lc-title')) return true;
    if (el.closest('[data-lc-t], [data-lc-ph], #modal-add')) return true;
    if (el.querySelector && el.querySelector('[data-lc-t], [data-lc-ph]')) return true;
    if (el.matches && el.matches(DOM_SKIP)) return true;
    if (el.closest && el.closest(DOM_SKIP)) return true;
    if (el.querySelector && el.querySelector('svg, img, input, select, button, .td-actions')) return true;
    return false;
  }

  function applyElText(el, lang) {
    if (shouldSkipEl(el)) return;
    if (el.tagName === 'INPUT' && el.placeholder) {
      if (lang === 'en') {
        /* نخزّن الأصل فقط لو لسه عربي — حتى لا نخزن نصاً مترجماً بالخطأ */
        if (!el.dataset.lcPhAr && AR.test(el.placeholder)) el.dataset.lcPhAr = el.placeholder;
        var ph = text(el.placeholder);
        if (ph !== el.placeholder) el.placeholder = ph;
      } else if (el.dataset.lcPhAr) {
        el.placeholder = el.dataset.lcPhAr;
        delete el.dataset.lcPhAr;
      }
      return;
    }
    var raw = el.textContent;
    if (!raw || !String(raw).trim()) return;
    if (lang === 'en') {
      if (el.dataset.lcAr == null && AR.test(raw)) el.dataset.lcAr = raw;
      var en = text(raw);
      if (en !== raw) el.textContent = en;
    } else if (el.dataset.lcAr != null) {
      el.textContent = el.dataset.lcAr;
      delete el.dataset.lcAr;
    }
  }

  /** تطبيق EN/AR على جداول وبادجات وعناوين — كل الصفحات */
  function applyDom(root, lang) {
    root = root || document;
    lang = lang || currentLang();
    root.querySelectorAll(DOM_TARGETS).forEach(function (el) {
      applyElText(el, lang);
    });
    applySearchPlaceholders(root, lang);
  }

  function refreshPage() {
    // إعادة رسم بسبب تغيير العرض/اللغة — تحافظ على صفحة الجدول الحالية
    global.__lcPreservePage = true;
    try {
      if (typeof global.__lcRefreshPage === 'function') global.__lcRefreshPage();
    } finally {
      global.__lcPreservePage = false;
    }
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
    if (!global.LiftCoreI18n || !global.LiftCoreI18n.setLang) return;
    if (global.setLang === global.LiftCoreI18n.setLang) return;
    try {
      global.setLang = global.LiftCoreI18n.setLang;
    } catch (e) { /* setLang قد يكون مقفولاً — استخدم LiftCoreI18n.setLang */ }
  }

  [0, 100, 400, 1000, 2500].forEach(function (ms) { setTimeout(lockGlobalSetLang, ms); });
  global.addEventListener('load', lockGlobalSetLang);

  /* ── رمز الريال السعودي U+20C1 ──
     أنظمة كثيرة (ويندوز 10 مثلاً) لا تملك الرمز في خطوطها.
     نغلّف كل ظهور نصي للرمز بـ <span class="lc-sar-char"> المربوط بخط الرمز. */
  var SAR_CHAR = '\u20C1';

  function wrapSarChars(root) {
    root = root || document.body;
    if (!root) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var nodes = [];
    var n;
    while ((n = walker.nextNode())) {
      if (n.textContent.indexOf(SAR_CHAR) === -1) continue;
      var p = n.parentElement;
      if (!p) continue;
      var tag = p.tagName;
      if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'TEXTAREA' || tag === 'OPTION' || tag === 'TITLE') continue;
      if (p.closest('.lc-sar-char')) continue;
      nodes.push(n);
    }
    nodes.forEach(function (node) {
      var parts = node.textContent.split(SAR_CHAR);
      var frag = document.createDocumentFragment();
      parts.forEach(function (part, i) {
        if (i) {
          var s = document.createElement('span');
          s.className = 'lc-sar-char';
          s.setAttribute('aria-label', 'ريال سعودي');
          s.textContent = SAR_CHAR;
          frag.appendChild(s);
        }
        if (part) frag.appendChild(document.createTextNode(part));
      });
      node.parentNode.replaceChild(frag, node);
    });
  }

  var sarTimer = null;
  function scheduleSarWrap() {
    clearTimeout(sarTimer);
    sarTimer = setTimeout(function () { wrapSarChars(document.body); }, 250);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleSarWrap);
  } else {
    scheduleSarWrap();
  }
  document.addEventListener('liftcore:lang', scheduleSarWrap);
  if (typeof MutationObserver !== 'undefined') {
    var sarMo = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var t = muts[i].target;
        if (t && t.textContent && t.textContent.indexOf(SAR_CHAR) !== -1) {
          scheduleSarWrap();
          return;
        }
      }
    });
    var startSarMo = function () {
      if (document.body) sarMo.observe(document.body, { childList: true, subtree: true, characterData: true });
    };
    if (document.body) startSarMo();
    else document.addEventListener('DOMContentLoaded', startSarMo);
  }

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
    fmtTransactionsCount: fmtTransactionsCount,
    fmtMargin: fmtMargin,
    fmtShowing: fmtShowing,
    fmtPageRange: fmtPageRange,
    setCountEl: setCountEl,
    applyDom: applyDom,
    refreshPage: refreshPage,
    ENUM: ENUM,
  };
})(window);
