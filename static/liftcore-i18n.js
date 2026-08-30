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
    '/technicians?tab=teams': { ar: 'فرق الصيانة', en: 'Maintenance Teams' },
    '/maintenance-visits': { ar: 'الصيانة', en: 'Maintenance' },
    '/faults': { ar: 'الأعطال', en: 'Faults' },
    '/parts-billing': { ar: 'تركيب قطع غيار', en: 'Parts Installation' },
    '/revenues': { ar: 'الإيرادات', en: 'Revenues' },
    '/expenses': { ar: 'المصروفات', en: 'Expenses' },
    '/accounts': { ar: 'شجرة الحسابات', en: 'Chart of Accounts' },
    '/journals': { ar: 'القيود اليومية', en: 'Journal Entries' },
    '/journals/new': { ar: 'قيد يدوي جديد', en: 'New Manual Journal' },
    '/ledger': { ar: 'دفتر الأستاذ', en: 'General Ledger' },
    '/trial-balance': { ar: 'ميزان المراجعة', en: 'Trial Balance' },
    '/pnl': { ar: 'قائمة الدخل', en: 'Income Statement' },
    '/balance-sheet': { ar: 'المركز المالي', en: 'Balance Sheet' },
    '/invoices': { ar: 'الفواتير', en: 'Invoices' },
    '/inventory': { ar: 'الأصناف', en: 'Inventory Items' },
    '/stock-movements': { ar: 'حركة المخزن', en: 'Stock Movements' },
    '/purchase-orders': { ar: 'طلبات الشراء', en: 'Purchase Orders' },
    '/elevator-estimates': { ar: 'تقدير تكلفة مصعد', en: 'Elevator Cost Estimate' },
    '/reports': { ar: 'التقارير', en: 'Reports' },
    '/reports/dashboard': { ar: 'تقرير الداشبورد', en: 'Dashboard Report' },
    '/reports/client-annual': { ar: 'التقرير السنوي للعميل', en: 'Client Annual Report' },
    '/reports/clients': { ar: 'تقرير العملاء', en: 'Clients Report' },
    '/reports/elevators': { ar: 'تقرير المصاعد', en: 'Elevators Report' },
    '/reports/contracts': { ar: 'تقرير العقود', en: 'Contracts Report' },
    '/reports/technicians': { ar: 'تقرير الفنيين', en: 'Technicians Report' },
    '/reports/maintenance-visits': { ar: 'تقرير زيارات الصيانة', en: 'Maintenance Visits Report' },
    '/reports/maintenance': { ar: 'تقرير الصيانة', en: 'Maintenance Report' },
    '/reports/faults': { ar: 'تقرير الأعطال', en: 'Faults Report' },
    '/reports/financial': { ar: 'التقرير المالي', en: 'Financial Report' },
    '/reports/contract-forecast': { ar: 'توقعات تحصيل العقود', en: 'Contract Collection Forecast' },
    '/reports/financial-health': { ar: 'الصحة المالية', en: 'Financial Health' },
    '/reports/billing-discrepancies': { ar: 'فروقات الفوترة', en: 'Billing Discrepancies' },
    '/reports/revenues': { ar: 'تقرير الإيرادات', en: 'Revenues Report' },
    '/reports/expenses': { ar: 'تقرير المصروفات', en: 'Expenses Report' },
    '/reports/invoices': { ar: 'تقرير الفواتير', en: 'Invoices Report' },
    '/reports/inventory': { ar: 'تقرير الأصناف', en: 'Inventory Report' },
    '/reports/stock': { ar: 'تقرير حركة المخزن', en: 'Stock Report' },
    '/reports/stock-movements': { ar: 'تقرير حركة المخزن', en: 'Stock Movements Report' },
    '/settings': { ar: 'الإعدادات', en: 'Settings' },
    '/installation/': { ar: 'لوحة المشاريع', en: 'Projects Home' },
    '/installation/leads': { ar: 'فرص البيع', en: 'Sales Leads' },
    '/installation/projects': { ar: 'المشاريع والتسعير', en: 'Projects & Pricing' },
  };

  var SECTIONS = {
    'الرئيسية': 'Main',
    'العملاء والعقود': 'Clients & Contracts',
    'الفريق الفني': 'Field Team',
    'فرق الصيانة': 'Maintenance Teams',
    'العمليات': 'Operations',
    'المالية': 'Finance',
    'إدارة المخازن': 'Warehouse',
    'المخزن': 'Inventory',
    'التقارير': 'Reports',
    'كل التقارير': 'All Reports',
    'تقارير إدارية': 'Management Reports',
    'تقارير البيانات': 'Data Reports',
    'تقارير مالية': 'Financial Reports',
    'تقارير المخزن': 'Warehouse Reports',
    'التركيب': 'Installation',
    'تركيب جديد': 'New Installation',
    'البيانات': 'Data',
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
    'العملاء والعقود': 'Clients & Contracts',
    'الفريق الفني': 'Field Team',
    'فرق الصيانة': 'Maintenance Teams',
    'البيانات': 'Data',
    'العمليات': 'Operations',
    'المالية': 'Finance',
    'إدارة المخازن': 'Warehouse',
    'المخزن': 'Inventory',
    'التقارير': 'Reports',
    'كل التقارير': 'All Reports',
    'تقارير إدارية': 'Management Reports',
    'تقارير البيانات': 'Data Reports',
    'تقارير مالية': 'Financial Reports',
    'تقارير المخزن': 'Warehouse Reports',
    'التركيب': 'Installation',
    'العملاء': 'Clients',
    'المصاعد': 'Elevators',
    'العقود': 'Contracts',
    'الفنيون': 'Technicians',
    'الفنيين': 'Technicians',
    'الصيانة': 'Maintenance',
    'الأعطال': 'Faults',
    'تركيب قطع غيار': 'Parts Installation',
    'الإيرادات': 'Revenues',
    'المصروفات': 'Expenses',
    'الفواتير': 'Invoices',
    'الأصناف': 'Inventory Items',
    'حركة المخزن': 'Stock Movements',
    'طلبات الشراء': 'Purchase Orders',
    'تقدير تكلفة مصعد': 'Elevator Cost Estimate',
    'تقدير تكلفة إنشاء مصعد': 'New Elevator Cost Estimate',
    'مواصفات المشروع': 'Project Specifications',
    'بنود التكلفة': 'Cost Line Items',
    'احسب التكلفة': 'Calculate Cost',
    'حفظ وطباعة': 'Save & Print',
    'التقديرات المحفوظة': 'Saved Estimates',
    'ابحث بالاسم أو الكود...': 'Search by name or code…',
    'لا توجد نتائج': 'No results',
    'مفتاح Google Maps (اختياري)': 'Google Maps API key (optional)',
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
    'على حساب الشركة': 'On Company Account',
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
    /* — جداول وعناوين الصفحات — */
    'الكود': 'Code',
    'اسم العميل': 'Client Name',
    'المدينة': 'City',
    'الحي': 'District',
    'الهاتف': 'Phone',
    'المصاعد': 'Elevators',
    'حالة العقد': 'Contract Status',
    'إجراءات': 'Actions',
    'الاسم': 'Name',
    'اسم الفني': 'Technician Name',
    'التخصص': 'Specialization',
    'طوارئ': 'Emergency',
    'المسمى الوظيفي': 'Job Title',
    'النوع': 'Type',
    'البداية': 'Start',
    'الانتهاء': 'End',
    'تاريخ البداية': 'Start Date',
    'تاريخ الانتهاء': 'End Date',
    'قيمة العقد': 'Contract Value',
    'حالة الفاتورة': 'Invoice Status',
    'الفاتورة': 'Invoice',
    'المبنى': 'Building',
    'الماركة': 'Brand',
    'الحمولة': 'Capacity',
    'الصيانة القادمة': 'Next Maintenance',
    'رقم العملية': 'Transaction #',
    'نوع الإيراد': 'Revenue Type',
    'نوع المصروف': 'Expense Type',
    'طريقة الدفع': 'Payment Method',
    'المبلغ (ر.س)': 'Amount (\u20C1)',
    'المبلغ (SAR)': 'Amount (SAR)',
    'العميل / العقد': 'Client / Contract',
    'رقم المستند': 'Document #',
    'البيان': 'Description',
    'اسم الصنف': 'Item Name',
    'التصنيف': 'Category',
    'الرصيد': 'Balance',
    'الحد الأدنى': 'Min Stock',
    'سعر الشراء': 'Purchase Price',
    'قيمة المخزون': 'Stock Value',
    'المورد': 'Supplier',
    'حالة الطلب': 'Order Status',
    'نوع العطل': 'Fault Type',
    'الأولوية': 'Priority',
    'الاستجابة': 'Response',
    'فوترة': 'Billing',
    'الوقت': 'Time',
    'رقم الحركة': 'Movement #',
    'الاتجاه': 'Direction',
    'نوع الحركة': 'Movement Type',
    'الصنف': 'Item',
    'الكمية': 'Quantity',
    'القيمة': 'Value',
    'الفني / المستلم': 'Technician / Recipient',
    'السبب': 'Reason',
    'السبب / الموقع': 'Reason / Location',
    'بيان القطع': 'Parts Description',
    'التكلفة': 'Cost',
    'سعر العميل': 'Client Price',
    'الربح': 'Profit',
    'المسؤول': 'Responsible',
    'عدد العقود': 'Contracts Count',
    'الأيام المتبقية': 'Days Remaining',
    'كود المصعد': 'Elevator Code',
    'آخر صيانة': 'Last Maintenance',
    'الفني المسؤول': 'Assigned Technician',
    'نوع الزيارة': 'Visit Type',
    'الأعمال المنفذة': 'Work Done',
    'آخر الزيارات': 'Recent Visits',
    'الأعطال المرتبطة': 'Related Faults',
    'قائمة العملاء': 'Clients List',
    'قائمة المصاعد': 'Elevators List',
    'قائمة العقود': 'Contracts List',
    'قائمة الفنيين': 'Technicians List',
    'سجل الصيانة': 'Maintenance Log',
    'سجل الأعطال': 'Faults Log',
    'خريطة العملاء': 'Clients Map',
    'إضافة عميل جديد': 'Add New Client',
    'إضافة مصعد جديد': 'Add New Elevator',
    'إضافة عقد جديد': 'Add New Contract',
    'إضافة فني جديد': 'Add New Technician',
    'تسجيل عطل': 'Register Fault',
    'تسجيل عطل جديد': 'Register New Fault',
    'تعديل العطل': 'Edit Fault',
    'حفظ وتعيين الفني': 'Save & Assign Technician',
    'إغلاق العطل': 'Close Fault',
    'طريقة الحل': 'Resolution',
    'قيد المعالجة': 'In Progress',
    'انتظار قطع': 'Awaiting Parts',
    'تم الاصلاح': 'Repaired',
    'محلول': 'Resolved',
    'اختر العميل': 'Select a client',
    'اختر المصعد': 'Select an elevator',
    'اختر فني واحد على الأقل': 'Select at least one technician',
    'حدد تاريخ الزيارة': 'Select visit date',
    'جاري الحفظ...': 'Saving…',
    'تسجيل زيارة': 'Register Visit',
    'فلترة متقدمة': 'Advanced Filter',
    'عرض الخريطة': 'Map View',
    'عرض القائمة': 'List View',
    'عرض البطاقات': 'Card View',
    'عرض الجدول': 'Table View',
    'نشط': 'Active',
    'غير نشط': 'Inactive',
    'معطّل': 'Disabled',
    'ساري': 'Valid',
    'منتهي': 'Expired',
    'محصل': 'Collected',
    'غير محصل': 'Uncollected',
    'على حساب الشركة': 'On Company Account',
    'عاجل': 'Urgent',
    'عادي': 'Normal',
    'مفتوح': 'Open',
    'مغلق': 'Closed',
    'قيد التنفيذ': 'In Progress',
    'مجدول': 'Scheduled',
    'مرسل': 'Dispatched',
    /* — الإعدادات — */
    'الشركة والهوية': 'Company & Branding',
    'المستخدمون': 'Users',
    'حسابي': 'My Account',
    'الباقة': 'Plan',
    'بيانات الشركة': 'Company Details',
    'الشعار والمقاس': 'Logo & Size',
    'بيانات حسابي': 'My Account Details',
    'تغيير كلمة المرور': 'Change Password',
    'مظهر البرنامج': 'App Appearance',
    'قائمة المستخدمين': 'Users List',
    'إضافة مستخدم جديد': 'Add New User',
    'المستخدم': 'Username',
    'الدور': 'Role',
    'آخر دخول': 'Last Login',
    'تفعيل': 'Enable',
    'تعطيل': 'Disable',
    'داكن': 'Dark',
    'فاتح': 'Light',
    'حفظ الإعدادات': 'Save Settings',
    'حفظ بيانات الشركة': 'Save Company',
    'حفظ البيانات': 'Save Profile',
    'حفظ المظهر': 'Save Theme',
    'تحديث كلمة المرور': 'Update Password',
    'إنشاء المستخدم': 'Create User',
    'حفظ التعديلات': 'Save Changes',
    'كلمة المرور الحالية *': 'Current Password *',
    'كلمة المرور الجديدة *': 'New Password *',
    'تأكيد كلمة المرور *': 'Confirm Password *',
  };

  if (global.__LC_TRANSLATIONS) {
    Object.keys(global.__LC_TRANSLATIONS).forEach(function (k) {
      TEXT[k] = global.__LC_TRANSLATIONS[k];
    });
  }
  if (global.__LC_I18N_UI) {
    Object.keys(global.__LC_I18N_UI).forEach(function (k) {
      TEXT[k] = global.__LC_I18N_UI[k];
    });
  }

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
    /* رمز الريال ⃁ ليس ترجمة تُعكس — يبقى كما هو في اللغتين */
    if (String(TEXT[ar]).indexOf('\u20C1') !== -1) return;
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
      /* جمل التنبيهات الديناميكية — قبل الأنماط العامة */
      .replace(/(\d+)\s*عطل حرج يحتاج تدخلاً فورياً/g, '$1 critical fault(s) need immediate action')
      .replace(/(\d+)\s*عطل بانتظار توفير قطع الغيار/g, '$1 fault(s) awaiting spare parts')
      .replace(/(\d+)\s*عطل تجاوز 48 ساعة بدون إغلاق/g, '$1 fault(s) open for over 48 hours')
      .replace(/(\d+)\s*طلب قطع غيار من الفنيين بانتظار المكتب/g, '$1 parts request(s) from technicians awaiting office')
      .replace(/(\d+)\s*عرض سعر بانتظار موافقة العميل/g, '$1 quotation(s) awaiting client approval')
      .replace(/هامش\s*([\d.]+)\s*%/g, 'Margin $1%')
      /* عبارات التقارير — قبل الأنماط العامة حتى لا تكسرها */
      .replace(/عرض\s+(\d+)\s*سجل/g, 'Showing $1 records')
      .replace(/(\d+)\s*تقرير متاح/g, '$1 reports available')
      .replace(/(\d+)\s*عميل جديد هذا العام/g, '$1 new clients this year')
      .replace(/(\d+)\s*مصعد جديد هذا العام/g, '$1 new elevators this year')
      .replace(/(\d+)\s*نشط حالياً/g, '$1 active now')
      .replace(/عن العام الماضي/g, 'vs last year')
      .replace(/هامش ربح/g, 'profit margin')
      .replace(/معدل التجديد/g, 'renewal rate')
      .replace(/نسبة الإنجاز/g, 'completion rate')
      .replace(/نسبة الحل/g, 'resolution rate')
      .replace(/تقرير سنوي شامل/g, 'Comprehensive Annual Report')
      .replace(/(\d+)\s*ساعات/g, '$1 hours')
      .replace(/([\d.]+)\s*ساعة/g, '$1 hr')
      .replace(/(\d+)\s*دقيقة/g, '$1 min')
      .replace(/(\d+)\s*يوم/g, '$1 days')
      .replace(/(\d+)\s*كجم/g, '$1 kg')
      .replace(/(\d+)\s*سجل/g, '$1 records')
      .replace(/(\d+)\s*عملية/g, '$1 transactions')
      .replace(/(\d+)\s*عمليات/g, '$1 transactions')
      .replace(/(\d+)\s*مصعد/g, '$1 elevators')
      .replace(/(\d+)\s*مصاعد/g, '$1 elevators')
      .replace(/(\d+)\s*عميل/g, '$1 clients')
      .replace(/(\d+)\s*عقد/g, '$1 contracts')
      .replace(/(\d+)\s*عطل/g, '$1 faults')
      .replace(/(\d+)\s*زيارة/g, '$1 visits')
      .replace(/(\d+)\s*فني/g, '$1 technicians')
      .replace(/(\d+)\s*فاتورة/g, '$1 invoices')
      .replace(/(\d+)\s*سند/g, '$1 receipts')
      .replace(/(\d+)\s*صنف/g, '$1 items')
      .replace(/(\d+)\s*أصناف/g, '$1 items')
      .replace(/(\d+)\s*حركة/g, '$1 movements')
      .replace(/(\d+)\s*عقود/g, '$1 contracts')
      .replace(/(\d+)\s*فواتير/g, '$1 invoices')
      .replace(/(\d+)\s*أعطال/g, '$1 faults')
      .replace(/(\d+)\s*زيارات/g, '$1 visits')
      .replace(/(\d+)\s*عملاء/g, '$1 clients')
      .replace(/([0-9.,]+)\s*قطعة/g, '$1 pcs')
      .replace(/([0-9.,]+)\s*متر/g, '$1 m')
      .replace(/([0-9.,]+)\s*لتر/g, '$1 L')
      .replace(/الطلبات السابقة\s*\((\d+)\)/g, 'Previous Orders ($1)')
      .replace(/عرض\s+(\d+)\s+من\s+(\d+)/g, 'Showing $1 of $2')
      .replace(/(\d+)\s*\/\s*(\d+)\s*خطوة/g, '$1 / $2 steps')
      .replace(/المهمة الحالية · (\d+) خطوة متبقية/g, 'Current task · $1 steps remaining')
      .replace(/جدول التنفيذ\s*\((\d+)%\)/g, 'Timeline ($1%)')
      .replace(/مرحلة\s+(\d+)/g, 'Phase $1')
      .replace(/الفرص المسجّلة\s*\((\d+)\)/g, 'Registered Leads ($1)')
      .replace(/متابعة التسعير\s*\(([^)]+)\)/g, 'Continue Pricing ($1)')
      .replace(/(\d+)%\s*من العقد/g, '$1% of contract');
  }

  function setNavItemLabel(link, lang) {
    var href = (link.getAttribute('href') || '').replace(/\/+$/, '') || '/';
    var pair = NAV_HREF[href] || NAV_HREF[href.split('?')[0]];
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

  function lookupEn(key) {
    return TEXT[key] || SECTIONS[key] || ROLES[key] || null;
  }

  function shouldSkipTextNode(node) {
    var p = node.parentElement;
    if (!p) return true;
    if (p.closest('#modal-add')) return true;
    if (p.closest('[data-i18n-skip], script, style, noscript, .lc-sar, .lc-sar-char')) return true;
    if (p.closest('[data-lc-t], .cloc-hint, .cloc-box')) return true;
    if (p.tagName === 'INPUT' || p.tagName === 'TEXTAREA' || p.tagName === 'SCRIPT') return true;
    /* نص أزرار الجداول (تعديل / حذف ...) يُترجم دائماً */
    if (p.closest('button')) return false;
    var td = p.closest('td');
    if (td && td.closest('tbody')) {
      if (td.classList.contains('lc-code') || td.classList.contains('lc-date') ||
          td.classList.contains('lc-num') || td.classList.contains('lc-elev') ||
          td.classList.contains('lc-contract')) return true;
      if (td.querySelector('a[href], input, select, button')) return true;
      var key = norm(node.textContent);
      /* كميات بالوحدات: 12 قطعة / 5 متر ... */
      if (/^[0-9٠-٩.,]+\s*(قطعة|متر|لتر|كجم)$/.test(key)) return false;
      if (!lookupEn(key) && !/^(نشط|غير نشط|منتهي|معلق|مكتمل|ملغى|عاجل|عادي|ساري|محصل|غير محصل|على حساب الشركة|مدفوعة|غير مدفوعة)$/.test(key)) {
        if (key.length > 40 || /[0-9]{2,}/.test(key)) return true;
      }
    }
    return false;
  }

  function walkTextNodes(root, lang) {
    if (!root) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var node;
    while ((node = walker.nextNode())) {
      if (shouldSkipTextNode(node)) continue;
      translateNode(node, lang);
    }
  }

  function shouldTranslateZone(el) {
    return true;
  }

  function applyLcMarked(root, lang) {
    if (!root) return;
    root.querySelectorAll('[data-lc-t]').forEach(function (el) {
      var key = el.getAttribute('data-lc-t');
      if (!key) return;
      if (lang === 'en') {
        if (el.dataset.lcAr == null) el.dataset.lcAr = el.textContent;
        var en = lookupEn(norm(key)) || t(key, 'en');
        if (en !== key) el.textContent = en;
      } else if (el.dataset.lcAr != null) {
        el.textContent = el.dataset.lcAr;
      }
    });
    root.querySelectorAll('[data-lc-ph]').forEach(function (el) {
      var key = el.getAttribute('data-lc-ph');
      if (!key) return;
      if (lang === 'en') {
        if (!el.dataset.lcPhAr) el.dataset.lcPhAr = el.getAttribute('placeholder') || '';
        var phEn = lookupEn(norm(key)) || t(key, 'en');
        if (phEn && phEn !== key) el.setAttribute('placeholder', phEn);
      } else if (el.dataset.lcPhAr) {
        el.setAttribute('placeholder', el.dataset.lcPhAr);
      }
    });
    root.querySelectorAll('option[data-lc-t]').forEach(function (el) {
      var optKey = el.getAttribute('data-lc-t');
      if (!optKey) return;
      if (lang === 'en') {
        if (el.dataset.lcAr == null) el.dataset.lcAr = el.textContent;
        var optEn = lookupEn(norm(optKey)) || t(optKey, 'en');
        if (optEn !== optKey) el.textContent = optEn;
      } else if (el.dataset.lcAr != null) {
        el.textContent = el.dataset.lcAr;
      }
    });
    root.querySelectorAll('[data-lc-title]').forEach(function (el) {
      var titleKey = el.getAttribute('data-lc-title');
      if (!titleKey) return;
      if (lang === 'en') {
        if (!el.dataset.lcTitleAr) el.dataset.lcTitleAr = el.getAttribute('title') || '';
        var titleEn = lookupEn(norm(titleKey)) || t(titleKey, 'en');
        if (titleEn && titleEn !== titleKey) el.setAttribute('title', titleEn);
      } else if (el.dataset.lcTitleAr) {
        el.setAttribute('title', el.dataset.lcTitleAr);
      }
    });
  }

  function translateFormAttributes(root, lang) {
    root.querySelectorAll('input[placeholder], textarea[placeholder]').forEach(function (el) {
      if (el.closest('#modal-add')) return;
      if (el.hasAttribute('data-lc-ph')) return;
      var ph = el.getAttribute('placeholder');
      if (!ph || !/[\u0600-\u06FF]/.test(ph)) return;
      if (lang === 'en') {
        if (!el.dataset.i18nPhAr) el.dataset.i18nPhAr = ph;
        var en = lookupEn(norm(ph));
        if (en) el.setAttribute('placeholder', en);
      } else if (el.dataset.i18nPhAr) {
        el.setAttribute('placeholder', el.dataset.i18nPhAr);
      }
    });
    root.querySelectorAll('option').forEach(function (el) {
      if (el.closest('#modal-add')) return;
      translateElement(el, lang);
    });
    root.querySelectorAll('[title]').forEach(function (el) {
      if (el.closest('#modal-add')) return;
      var ti = el.getAttribute('title');
      if (!ti || !/[\u0600-\u06FF]/.test(ti)) return;
      if (lang === 'en') {
        if (!el.dataset.i18nTitleAr) el.dataset.i18nTitleAr = ti;
        var en = lookupEn(norm(ti));
        if (en) el.setAttribute('title', en);
      } else if (el.dataset.i18nTitleAr) {
        el.setAttribute('title', el.dataset.i18nTitleAr);
      }
    });
  }

  function translateNode(node, lang) {
    if (!node) return;
    var raw = node.textContent;
    var key = norm(raw);
    if (!key) return;

    if (lang === 'en') {
      if (!storedAr.has(node)) storedAr.set(node, raw);
      var en = lookupEn(key) || translateRecordCount(raw, 'en');
      if (en !== raw) node.textContent = en;
      else if (/سجل|عملية|مصعد|عميل|عقد|عرض/.test(raw)) node.textContent = translateRecordCount(raw, 'en');
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

  function translateElement(el, lang) {
    if (!el || el.closest('[data-i18n-skip]')) return;
    if (el.hasAttribute('data-i18n')) return;
    if (el.classList && el.classList.contains('page-title')) {
      translateMixed(el, lang);
      return;
    }
    var tag = (el.tagName || '').toUpperCase();
    if (el.querySelector('svg')) {
      translateMixed(el, lang);
      return;
    }
    if (el.children && el.children.length > 0) {
      translateMixed(el, lang);
      return;
    }
    if (el.querySelector('input, select, textarea, button')) {
      if (tag === 'LABEL') translateMixed(el, lang);
      return;
    }
    if (tag === 'TH' || tag === 'TD') {
      translateMixed(el, lang);
      if (!el.querySelector('*')) replaceExact(el, lang);
      return;
    }
    if (tag === 'OPTION') {
      replaceExact(el, lang);
      return;
    }
    replaceExact(el, lang);
  }

  function applySelectors(root, lang) {
    var selectors = [
      '.nav-section',
      '.nav-group-label',
      '.nav-group-btn',
      '.nav-menu-section',
      '.nav-item',
      '.lc-back-link',
      '.header-page-title',
      '.page-title',
      '.page-heading',
      '.stat-label',
      '.section-title',
      '.card-section-title',
      '.modal-title',
      '.profile-dropdown a',
      '.profile-dropdown-name',
      '.profile-dropdown-role',
      '.btn',
      '.tab:not(.lang-opt)',
      '.tabs .tab',
      '.stat-mini-label',
      '.alert-chip',
      '.legend-item',
      '.cal-title',
      '.alert-expiry',
      '.form-section-title',
      'label',
      'th',
      'h1',
      'h2',
      'h3',
      '.toolbar-title',
      '.filter-label',
      '.hint',
      '.field-hint',
      '.map-picker-hint',
      '.map-picker-coords',
      'option',
      '.panel-title',
      '.exec-aside-title',
      '.exec-hero-label',
      '.exec-hero-hint',
      '.exec-hero-phase',
      '.exec-auto-lbl',
      '.exec-auto-note',
      '.exec-done-panel h2',
      'summary',
      '.rpt-stat-label',
      '.rpt-header-logo-sub',
      '.rpt-footer-line span',
      '.print-toolbar-title',
    ];
    selectors.forEach(function (sel) {
      root.querySelectorAll(sel).forEach(function (el) {
        if (el.closest('#modal-add')) return;
        translateElement(el, lang);
      });
    });

    root.querySelectorAll('.main, .wrap').forEach(function (scope) {
      scope.querySelectorAll('p, span.badge, .stat-val-label').forEach(function (el) {
        if (!el.children.length || (el.children.length === 1 && el.querySelector('.lc-sar'))) {
          translateElement(el, lang);
        }
      });
    });

    root.querySelectorAll('.nav-item[href]').forEach(function (a) {
      setNavItemLabel(a, lang);
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

  function lcTr(key, lang) {
    if (!key) return key;
    if (lang !== 'en') return key;
    return lookupEn(norm(key)) || key;
  }

  function captureLcArEl(el) {
    if (!el || el.dataset.lcAr != null) return;
    var t = el.textContent.replace(/\s+/g, ' ').trim();
    if (t) el.dataset.lcAr = t;
    if (el.innerHTML && el.querySelector('code')) el.dataset.lcArHtml = el.innerHTML;
  }

  function applyLcMarked(root, lang) {
    if (!root) root = document;
    if (lang !== 'ar' && lang !== 'en') lang = 'ar';
    root.querySelectorAll('[data-lc-ar]').forEach(function (el) {
      if (el.closest('[data-i18n-skip]') && !el.closest('[data-lc-server-i18n]')) return;
      captureLcArEl(el);
      if (lang === 'en') {
        var en = lcTr(el.dataset.lcAr, lang);
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') el.placeholder = en;
        else el.textContent = en;
      } else if (el.dataset.lcArHtml) {
        el.innerHTML = el.dataset.lcArHtml;
      } else {
        el.textContent = el.dataset.lcAr;
      }
    });
    root.querySelectorAll('[data-lc-t]').forEach(function (el) {
      var key = el.getAttribute('data-lc-t');
      if (!key) return;
      if (el.dataset.lcAr == null) el.dataset.lcAr = key;
      var label = lang === 'en' ? lcTr(key, lang) : el.dataset.lcAr;
      var sortInd = el.querySelector('.sort-ind');
      el.textContent = label;
      if (sortInd) {
        el.appendChild(document.createTextNode(' '));
        el.appendChild(sortInd);
      }
    });
    root.querySelectorAll('[data-lc-ph-ar]').forEach(function (el) {
      if (el.dataset.lcPhAr == null) el.dataset.lcPhAr = el.getAttribute('data-lc-ph-ar');
      el.placeholder = lang === 'en' ? lcTr(el.dataset.lcPhAr, lang) : el.dataset.lcPhAr;
    });
    root.querySelectorAll('[data-lc-map-t]').forEach(function (el) {
      var key = el.getAttribute('data-lc-map-t');
      if (!key) return;
      if (el.dataset.lcAr == null) el.dataset.lcAr = key;
      el.textContent = lang === 'en' ? lcTr(key, lang) : el.dataset.lcAr;
    });
  }

  var applying = false;
  var moTimer = null;

  function applyToRoot(root, lang) {
    if (!root) return;
    if (lang !== 'ar' && lang !== 'en') lang = 'ar';
    applyLcMarked(root, lang);
    applySelectors(root, lang);
    walkTextNodes(root, lang);
    translateFormAttributes(root, lang);
    if (global.LiftCoreDisplay && global.LiftCoreDisplay.applyDom) {
      global.LiftCoreDisplay.applyDom(root, lang);
    }
    applyLcMarked(root, lang);
  }

  function applyModal(modalId) {
    var el = typeof modalId === 'string' ? document.getElementById(modalId) : modalId;
    if (!el) return;
    if (el.hasAttribute && el.hasAttribute('data-lc-server-i18n')) return;
    var lang = global.__LC_LANG || currentLang || 'ar';
    if (lang !== 'en') return;
    applyToRoot(el, 'en');
    setTimeout(function () { applyToRoot(el, 'en'); }, 60);
    setTimeout(function () { applyToRoot(el, 'en'); }, 300);
  }

  function applyLanguage(lang) {
    if (applying) return;
    applying = true;
    try {
    if (lang !== 'ar' && lang !== 'en') lang = 'ar';
    currentLang = lang;
    global.__LC_LANG = lang;
    var root = document.documentElement;
    root.setAttribute('lang', lang);
    root.setAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr');
    try { localStorage.setItem('liftcore_lang', lang); } catch (e) { /* ignore */ }

    var ar = document.getElementById('btn-ar');
    var enBtn = document.getElementById('btn-en');
    if (ar) ar.classList.toggle('active', lang === 'ar');
    if (enBtn) enBtn.classList.toggle('active', lang === 'en');

    applyDataI18n(document, lang);
    applyLcMarked(document, lang);
    applySelectors(document, lang);

    var zones = document.querySelectorAll(
      '.sidebar, .main, .content, .wrap, .lc-header, .modal, .modal-overlay, .page-wrap, .card, .modal-body, .modal-content'
    );
    zones.forEach(function (z) {
      if (!shouldTranslateZone(z)) return;
      walkTextNodes(z, lang);
      translateFormAttributes(z, lang);
    });
    if (!zones.length) {
      walkTextNodes(document.body, lang);
      translateFormAttributes(document.body, lang);
    }

    updateHeaderDate(lang);

    if (global.LiftCoreDisplay && global.LiftCoreDisplay.applyDom) {
      global.LiftCoreDisplay.applyDom(document, lang);
    }

    document.dispatchEvent(new CustomEvent('liftcore:lang', { detail: { lang: lang } }));

    /* بعض الصفحات تعيد كتابة نصوص عربية في معالجات الحدث أعلاه — نترجم مرة أخيرة */
    zones.forEach(function (z) {
      if (!shouldTranslateZone(z)) return;
      walkTextNodes(z, lang);
    });

    document.querySelectorAll('.modal-overlay.open').forEach(function (m) {
      applyToRoot(m, lang);
    });

    if (typeof global.__lcApplyClientModal === 'function') {
      try { global.__lcApplyClientModal(); } catch (e) { /* ignore */ }
    }
    } finally {
      applying = false;
    }
  }

  function persistLanguage(lang) {
    return fetch('/api/user/language', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify({ lang: lang }),
      credentials: 'same-origin',
    }).catch(function () { /* offline / login page */ });
  }

  function setLang(lang) {
    var loginLang = document.getElementById('login-lang');
    if (loginLang) loginLang.value = lang;
    try { localStorage.setItem('liftcore_lang', lang); } catch (e) { /* ignore */ }

    var path = (global.location && global.location.pathname) || '';
    var portalPage = path === '/home' || path.indexOf('/departments/') === 0;

    /* منصات الأقسام: المحتوى يُعرض من السيرفر حسب اللغة */
    if (portalPage && lang !== currentLang && !loginLang) {
      var reloadPortal = function () { global.location.reload(); };
      var portalPersist = persistLanguage(lang);
      if (portalPersist && portalPersist.then) { portalPersist.then(reloadPortal, reloadPortal); }
      else { setTimeout(reloadPortal, 200); }
      return;
    }

    /* تبديل اللغة: إعادة تحميل لضمان تطبيق الترجمة/الاسترجاع بالكامل */
    if (lang !== currentLang && !loginLang) {
      var reloadForLang = function () { global.location.reload(); };
      var p = persistLanguage(lang);
      if (p && p.then) { p.then(reloadForLang, reloadForLang); }
      else { setTimeout(reloadForLang, 200); }
      return;
    }

    applyLanguage(lang);
    persistLanguage(lang);
  }

  function installSetLang() {
    try {
      if (global.setLang !== setLang) global.setLang = setLang;
    } catch (e) { /* ignore */ }
    global.LiftCoreI18n = {
      apply: applyLanguage,
      applyModal: applyModal,
      applyToRoot: applyToRoot,
      applyLcMarked: applyLcMarked,
      setLang: setLang,
      t: t,
      TEXT: TEXT,
      KEYS: KEYS,
      applyLcMarked: applyLcMarked,
      applyModal: applyModal,
    };
  }

  /* أزرار EN/AR — تشتغل حتى لو الصفحة عرّفت setLang قديم */
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.id) return;
    if (t.id === 'btn-ar') {
      e.preventDefault();
      e.stopPropagation();
      setLang('ar');
    } else if (t.id === 'btn-en') {
      e.preventDefault();
      e.stopPropagation();
      setLang('en');
    }
  }, true);

  function initLanguage() {
    var lang = global.__LC_LANG;
    if (!lang) {
      try { lang = localStorage.getItem('liftcore_lang'); } catch (e) { lang = null; }
    }
    if (lang !== 'ar' && lang !== 'en') lang = 'ar';
    applyLanguage(lang);
  }

  installSetLang();

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLanguage);
  } else {
    initLanguage();
  }
  window.addEventListener('load', function () {
    installSetLang();
    applyLanguage(currentLang);
    setTimeout(function () { installSetLang(); applyLanguage(currentLang); }, 400);
    setTimeout(function () { installSetLang(); applyLanguage(currentLang); }, 1200);
    setTimeout(function () { installSetLang(); applyLanguage(currentLang); }, 2500);
  });

  if (typeof MutationObserver !== 'undefined') {
    var mo = new MutationObserver(function () {
      if (currentLang !== 'en' || applying) return;
      clearTimeout(moTimer);
      moTimer = setTimeout(function () { applyLanguage('en'); }, 300);
    });
    if (document.body) {
      mo.observe(document.body, { childList: true, subtree: true });
    } else {
      document.addEventListener('DOMContentLoaded', function () {
        mo.observe(document.body, { childList: true, subtree: true });
      });
    }
  }
})(window);
