/**
 * LiftCore — ترجمة الواجهة (عربي / English)
 */
(function (global) {
  'use strict';

  var NAV_HREF = {
    '/dashboard': { ar: 'لوحة التحكم', en: 'Dashboard' },
    '/clients': { ar: 'العملاء', en: 'Clients' },
    '/elevators': { ar: 'المصاعد', en: 'Elevators' },
    '/contracts': { ar: 'العقود', en: 'Contracts' },
    '/technicians': { ar: 'الفنيون', en: 'Technicians' },
    '/maintenance-visits': { ar: 'الصيانة', en: 'Maintenance' },
    '/faults': { ar: 'الأعطال', en: 'Faults' },
    '/parts-billing': { ar: 'تركيب قطع غيار', en: 'Parts Installation' },
    '/revenues': { ar: 'الإيرادات', en: 'Revenues' },
    '/expenses': { ar: 'المصروفات', en: 'Expenses' },
    '/invoices': { ar: 'الفواتير', en: 'Invoices' },
    '/inventory': { ar: 'الأصناف', en: 'Inventory Items' },
    '/stock-movements': { ar: 'حركة المخزن', en: 'Stock Movements' },
    '/purchase-orders': { ar: 'طلبات الشراء', en: 'Purchase Orders' },
    '/reports': { ar: 'التقارير', en: 'Reports' },
    '/settings': { ar: 'الإعدادات', en: 'Settings' },
  };

  var SECTIONS = {
    'الرئيسية': 'Main',
    'البيانات': 'Data',
    'العمليات': 'Operations',
    'المالية': 'Finance',
    'المخزن': 'Inventory',
    'التقارير': 'Reports',
  };

  var ROLES = {
    'مدير النظام': 'System Admin',
    'مدير عمليات': 'Operations Manager',
    'عرض فقط': 'View Only',
  };

  /** نص عربي → إنجليزي (مطابقة تامة بعد trim) */
  var TEXT = {
    '← لوحة التحكم': '← Dashboard',
    'لوحة التحكم': 'Dashboard',
    'الإعدادات': 'Settings',
    'تعديل البروفايل': 'Edit Profile',
    'المظهر': 'Appearance',
    'تسجيل الخروج': 'Log Out',
    'مستخدم': 'User',
    'شاشة كاملة': 'Full Screen',
    'خروج من الشاشة الكاملة': 'Exit Full Screen',
    'الرئيسية': 'Main',
    'البيانات': 'Data',
    'العمليات': 'Operations',
    'المالية': 'Finance',
    'المخزن': 'Inventory',
    'التقارير': 'Reports',
    'العملاء': 'Clients',
    'المصاعد': 'Elevators',
    'العقود': 'Contracts',
    'الفنيون': 'Technicians',
    'الصيانة': 'Maintenance',
    'الأعطال': 'Faults',
    'تركيب قطع غيار': 'Parts Installation',
    'الإيرادات': 'Revenues',
    'المصروفات': 'Expenses',
    'الفواتير': 'Invoices',
    'الأصناف': 'Inventory Items',
    'حركة المخزن': 'Stock Movements',
    'طلبات الشراء': 'Purchase Orders',
    'إضافة': 'Add',
    'إضافة إيراد': 'Add Revenue',
    'إضافة مصروف': 'Add Expense',
    'إضافة عميل': 'Add Client',
    'إضافة مصعد': 'Add Elevator',
    'إضافة عقد': 'Add Contract',
    'إضافة فني': 'Add Technician',
    'إضافة صنف': 'Add Item',
    'تصدير Excel': 'Export Excel',
    'تصدير': 'Export',
    'بحث': 'Search',
    'بحث...': 'Search...',
    'فلترة': 'Filter',
    'مسح': 'Clear',
    'حفظ': 'Save',
    'إلغاء': 'Cancel',
    'إغلاق': 'Close',
    'حذف': 'Delete',
    'تعديل': 'Edit',
    'عرض': 'View',
    'طباعة': 'Print',
    'تأكيد': 'Confirm',
    'نعم': 'Yes',
    'لا': 'No',
    'الكل': 'All',
    'من': 'From',
    'إلى': 'To',
    'التاريخ': 'Date',
    'الحالة': 'Status',
    'الإجراءات': 'Actions',
    'ملاحظات': 'Notes',
    'الوصف': 'Description',
    'المبلغ': 'Amount',
    'الإجمالي': 'Total',
    'الضريبة': 'Tax',
    'الضريبة (15%)': 'Tax (15%)',
    'العميل': 'Client',
    'الفني': 'Technician',
    'المصعد': 'Elevator',
    'العقد': 'Contract',
    'نشط': 'Active',
    'منتهي': 'Expired',
    'معلق': 'Pending',
    'مكتمل': 'Completed',
    'ملغى': 'Cancelled',
    'غير محصل': 'Uncollected',
    'إجمالي الإيرادات': 'Total Revenues',
    'تجديد عقود': 'Contract Renewals',
    'قطع غيار': 'Spare Parts',
    'عقود جديدة': 'New Contracts',
    'سجل': 'records',
    'عملية': 'transaction',
    'عمليات': 'transactions',
    '0 سجل': '0 records',
    'تسجيل الدخول': 'Sign In',
    'دخول': 'Sign In',
    'كلمة المرور': 'Password',
    'البريد الإلكتروني أو اسم المستخدم': 'Email or username',
    'نسيت كلمة المرور؟': 'Forgot password?',
    'اسم المستخدم أو كلمة المرور غير صحيحة': 'Invalid username or password',
    'تم الحفظ بنجاح.': 'Saved successfully.',
  };

  var KEYS = {
    settings: { ar: 'الإعدادات', en: 'Settings' },
    fullscreen: { ar: 'شاشة كاملة', en: 'Full Screen' },
    fullscreen_exit: { ar: 'خروج من الشاشة الكاملة', en: 'Exit Full Screen' },
    back_dashboard: { ar: '← لوحة التحكم', en: '← Dashboard' },
    edit_profile: { ar: 'تعديل البروفايل', en: 'Edit Profile' },
    appearance: { ar: 'المظهر', en: 'Appearance' },
    logout: { ar: 'تسجيل الخروج', en: 'Log Out' },
    user: { ar: 'مستخدم', en: 'User' },
    login_email: { ar: 'البريد الإلكتروني أو اسم المستخدم', en: 'Email or username' },
    login_password: { ar: 'كلمة المرور', en: 'Password' },
    login_forgot: { ar: 'نسيت كلمة المرور؟', en: 'Forgot password?' },
    login_submit: { ar: 'دخول', en: 'Sign In' },
  };

  var REVERSE = {};
  Object.keys(TEXT).forEach(function (ar) {
    REVERSE[TEXT[ar]] = ar;
  });
  Object.keys(SECTIONS).forEach(function (ar) {
    REVERSE[SECTIONS[ar]] = ar;
  });
  Object.keys(ROLES).forEach(function (ar) {
    REVERSE[ROLES[ar]] = ar;
  });
  Object.values(NAV_HREF).forEach(function (pair) {
    REVERSE[pair.en] = pair.ar;
  });

  var storedAr = new WeakMap();
  var currentLang = 'ar';

  function norm(s) {
    return String(s || '').replace(/\s+/g, ' ').trim();
  }

  function t(arText, lang) {
    lang = lang || currentLang;
    if (lang === 'en') return TEXT[arText] || arText;
    return arText;
  }

  function translateRecordCount(text, lang) {
    if (lang !== 'en') return text;
    return String(text)
      .replace(/(\d+)\s*سجل/g, '$1 records')
      .replace(/(\d+)\s*عملية/g, '$1 transactions')
      .replace(/(\d+)\s*عمليات/g, '$1 transactions');
  }

  function setNavItemLabel(link, lang) {
    var path = (link.getAttribute('href') || '').split('?')[0];
    var pair = NAV_HREF[path];
  if (!pair) return;
    var label = lang === 'en' ? pair.en : pair.ar;
    var span = link.querySelector('span');
    if (span) {
      span.textContent = label;
      return;
    }
    var svg = link.querySelector('svg');
    var nodes = Array.prototype.slice.call(link.childNodes);
    nodes.forEach(function (n) {
      if (n.nodeType === 3) link.removeChild(n);
    });
    if (svg) {
      link.appendChild(document.createTextNode(label));
    } else {
      link.textContent = label;
    }
  }

  function translateNode(node, lang) {
    if (!node) return;
    var raw = node.textContent;
    var key = norm(raw);
    if (!key) return;

    if (lang === 'en') {
      if (!storedAr.has(node)) storedAr.set(node, raw);
      var en = TEXT[key] || SECTIONS[key] || ROLES[key] || translateRecordCount(raw, 'en');
      if (en !== raw) node.textContent = en;
      else if (/سجل|عملية/.test(raw)) node.textContent = translateRecordCount(raw, 'en');
    } else if (storedAr.has(node)) {
      node.textContent = storedAr.get(node);
    } else if (REVERSE[key]) {
      node.textContent = REVERSE[key];
    }
  }

  function replaceExact(el, lang) {
    if (!el || el.closest('[data-i18n-skip]')) return;
    translateNode(el, lang);
  }

  function translateMixed(el, lang) {
    if (!el || el.closest('[data-i18n-skip]')) return;
    if (el.hasAttribute('data-i18n')) return;
    Array.prototype.slice.call(el.childNodes).forEach(function (n) {
      if (n.nodeType === 3) translateNode(n, lang);
    });
  }

  function applyDataI18n(root, lang) {
    root.querySelectorAll('[data-i18n]').forEach(function (el) {
      var k = el.getAttribute('data-i18n');
      if (KEYS[k]) el.textContent = KEYS[k][lang] || KEYS[k].ar;
    });
    root.querySelectorAll('[data-i18n-title]').forEach(function (el) {
      var k = el.getAttribute('data-i18n-title');
      if (KEYS[k]) el.setAttribute('title', KEYS[k][lang] || KEYS[k].ar);
    });
    root.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
      var k = el.getAttribute('data-i18n-placeholder');
      if (KEYS[k]) el.setAttribute('placeholder', KEYS[k][lang] || KEYS[k].ar);
    });
  }

  function applySelectors(root, lang) {
    var selectors = [
      '.nav-section',
      '.nav-item',
      '.lc-back-link',
      '.header-page-title',
      '.page-title',
      '.page-heading',
      '.stat-label',
      '.section-title',
      '.modal-title',
      '.profile-dropdown a',
      '.profile-dropdown-name',
      '.profile-dropdown-role',
      '.btn',
      '.tab',
      '.flash',
      'label',
      'th',
    ];
    selectors.forEach(function (sel) {
      root.querySelectorAll(sel).forEach(function (el) {
        if (el.querySelector('svg')) {
          translateMixed(el, lang);
        } else if (!el.querySelector('input, select, textarea')) {
          replaceExact(el, lang);
        }
      });
    });

    root.querySelectorAll('.nav-item[href]').forEach(function (a) {
      setNavItemLabel(a, lang);
    });
    root.querySelectorAll('.nav-section').forEach(function (el) {
      replaceExact(el, lang);
    });
  }

  function updateHeaderDate(lang) {
    document.querySelectorAll('#h-date').forEach(function (el) {
      if (!global.LiftCoreFormat) return;
      var suffix = el.getAttribute('data-suffix');
      if (suffix == null) suffix = lang === 'en' ? ' — ' : ' — ';
      if (lang === 'en') {
        try {
          var d = new Date();
          el.textContent = new Intl.DateTimeFormat('en-US', {
            weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
          }).format(d);
        } catch (e) {
          global.LiftCoreFormat.setHeaderDate(el, new Date(), suffix);
        }
      } else {
        global.LiftCoreFormat.setHeaderDate(el, new Date(), suffix);
      }
    });
  }

  function applyLanguage(lang) {
    if (lang !== 'ar' && lang !== 'en') lang = 'ar';
    currentLang = lang;
    var root = document.documentElement;
    root.setAttribute('lang', lang);
    root.setAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr');
    try { localStorage.setItem('liftcore_lang', lang); } catch (e) { /* ignore */ }

    var ar = document.getElementById('btn-ar');
    var en = document.getElementById('btn-en');
    if (ar) ar.classList.toggle('active', lang === 'ar');
    if (en) en.classList.toggle('active', lang === 'en');

    applyDataI18n(document, lang);
    applySelectors(document, lang);
    updateHeaderDate(lang);

    document.dispatchEvent(new CustomEvent('liftcore:lang', { detail: { lang: lang } }));
  }

  function persistLanguage(lang) {
    fetch('/api/user/language', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify({ lang: lang }),
      credentials: 'same-origin',
    }).catch(function () { /* offline / login page */ });
  }

  function setLang(lang) {
    applyLanguage(lang);
    var loginLang = document.getElementById('login-lang');
    if (loginLang) loginLang.value = lang;
    persistLanguage(lang);
  }

  function initLanguage() {
    var lang = global.__LC_LANG;
    if (!lang) {
      try { lang = localStorage.getItem('liftcore_lang'); } catch (e) { lang = null; }
    }
    if (lang !== 'ar' && lang !== 'en') lang = 'ar';
    applyLanguage(lang);
  }

  global.LiftCoreI18n = {
    apply: applyLanguage,
    setLang: setLang,
    t: t,
    TEXT: TEXT,
    KEYS: KEYS,
  };

  global.setLang = setLang;

  /* صفحات قديمة تعرّف setLang محلياً في آخر الصفحة — نستعيد النسخة الكاملة بعد التحميل */
  function bindSetLang() {
    global.setLang = setLang;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLanguage);
  } else {
    initLanguage();
  }
  window.addEventListener('load', function () {
    bindSetLang();
    applyLanguage(currentLang);
  });
})(window);
