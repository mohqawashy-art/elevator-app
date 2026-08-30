"""منصات الأقسام — تعريفات /home و /departments/<slug>."""

from __future__ import annotations

HOME_UI = {
    'ar': {
        'page_title': 'منصات العمل',
        'kicker': 'اختر القسم',
        'title': 'منصات LiftCore',
        'subtitle': 'كل قسم له عملاؤه وعقوده وعملياته وتقاريره في مكان واحد.',
        'enter': 'دخول المنصة ←',
        'empty': 'لا توجد منصات متاحة لصلاحيات حسابك.',
    },
    'en': {
        'page_title': 'Work Platforms',
        'kicker': 'Choose a department',
        'title': 'LiftCore Platforms',
        'subtitle': 'Each department has its clients, contracts, operations, and reports in one place.',
        'enter': 'Enter platform →',
        'empty': 'No platforms are available for your account permissions.',
    },
}

PORTAL_UI = {
    'ar': {
        'back': '→ الرجوع إلى منصات العمل',
        'label': 'منصة متخصصة',
        'ops_title': 'العمل والعمليات',
        'ops_count': '{n} تبويبات',
        'reports_title': 'تقارير المنصة',
        'reports_count': '{n} تقارير',
        'no_links': 'لا توجد تبويبات متاحة لصلاحيات حسابك.',
        'no_reports': 'لا توجد تقارير متاحة لصلاحيات حسابك.',
    },
    'en': {
        'back': '← Back to platforms',
        'label': 'Department platform',
        'ops_title': 'Operations',
        'ops_count': '{n} tabs',
        'reports_title': 'Platform reports',
        'reports_count': '{n} reports',
        'no_links': 'No tabs available for your account permissions.',
        'no_reports': 'No reports available for your account permissions.',
    },
}

DEPARTMENT_PORTALS = {
    'maintenance': {
        'title': 'منصة الصيانة والأعطال',
        'title_en': 'Maintenance & Faults Platform',
        'short_title': 'الصيانة والأعطال',
        'short_title_en': 'Maintenance & Faults',
        'description': 'عملاء وعقود الصيانة والزيارات والبلاغات وقطع الغيار',
        'description_en': 'Maintenance clients, contracts, visits, reports, and spare parts',
        'color': '#2a7fff',
        'links': (
            ('عملاء الصيانة', 'Maintenance Clients', '/clients?scope=maintenance', 'clients.read'),
            ('عقود الصيانة', 'Maintenance Contracts', '/contracts?scope=maintenance', 'contracts.read'),
            ('مصاعد الصيانة', 'Maintenance Elevators', '/elevators', 'elevators.read'),
            ('زيارات الصيانة', 'Maintenance Visits', '/maintenance-visits', 'maintenance_visits.read'),
            ('الأعطال والبلاغات', 'Faults & Reports', '/faults', 'faults.read'),
            ('تركيب قطع الغيار', 'Parts Installation', '/parts-billing', 'parts_billing.read'),
        ),
        'reports': (
            ('تقرير زيارات الصيانة', 'Maintenance Visits Report', '/reports/maintenance-visits', 'report_maintenance.read'),
            ('تقرير الأعطال', 'Faults Report', '/reports/faults', 'report_faults.read'),
            ('تقرير العقود', 'Contracts Report', '/reports/contracts', 'report_contracts.read'),
            ('تقرير المصاعد', 'Elevators Report', '/reports/elevators', 'report_elevators.read'),
        ),
    },
    'installations': {
        'title': 'منصة التركيبات والتحديث',
        'title_en': 'Installations & Modernization Platform',
        'short_title': 'التركيبات والتحديث',
        'short_title_en': 'Installations & Modernization',
        'description': 'عملاء وعقود التركيبات ومشروعات التنفيذ والمتابعة',
        'description_en': 'Installation clients, contracts, execution projects, and follow-up',
        'color': '#c8a055',
        'links': (
            ('عملاء التركيبات', 'Installation Clients', '/clients?scope=installation', 'clients.read'),
            ('مشروعات التركيبات', 'Installation Projects', '/installation/projects', 'installation_projects.read', True),
            ('عقود التركيبات والتحديث', 'Installation Contracts', '/contracts?scope=installation', 'contracts.read'),
        ),
        'reports': (
            ('بطاقات وتقارير المشروعات', 'Project Cards & Reports', '/installation/projects', 'installation_projects.read', True),
            ('تقرير العقود', 'Contracts Report', '/reports/contracts', 'report_contracts.read'),
        ),
    },
    'marketing': {
        'title': 'منصة التسويق والمبيعات',
        'title_en': 'Marketing & Sales Platform',
        'short_title': 'التسويق والمبيعات',
        'short_title_en': 'Marketing & Sales',
        'description': 'لوحة المبيعات وعروض التركيب والصيانة والتقدير وفرص البيع',
        'description_en': 'Sales dashboard, installation and maintenance quotes, estimates, and sales leads',
        'color': '#14b8a6',
        'links': (
            ('لوحة المبيعات', 'Sales Dashboard', '/sales/', 'sales_quotes.read'),
            ('تركيب مصعد جديد', 'New Elevator Installation', '/sales/install/quotes/new', 'installation_projects.read', True),
            ('عرض سعر تحديث', 'Modernization Quote', '/sales/install/quotes/upgrade', 'installation_projects.read', True),
            ('إضافة أدوار', 'Add Floors Quote', '/sales/install/quotes/extend', 'installation_projects.read', True),
            ('عروض التركيب', 'Installation Quotes', '/sales/quotes?kind=install', 'installation_projects.read', True),
            ('عرض صيانة جديد', 'New Maintenance Quote', '/sales/maintenance-quotes/new', 'sales_quotes.read'),
            ('عروض الصيانة', 'Maintenance Quotes', '/sales/maintenance-quotes', 'sales_quotes.read'),
            ('تقدير تكلفة مصعد', 'Elevator Cost Estimate', '/elevator-estimates', 'elevator_estimates.read'),
            ('فرص البيع', 'Sales Leads', '/installation/leads', 'installation_projects.read', True),
        ),
        'reports': (
            ('تقرير العملاء', 'Clients Report', '/reports/clients', 'report_clients.read'),
            ('تقرير العقود', 'Contracts Report', '/reports/contracts', 'report_contracts.read'),
        ),
    },
    'inventory': {
        'title': 'منصة المخازن والمشتريات',
        'title_en': 'Warehouses & Purchasing Platform',
        'short_title': 'المخازن والمشتريات',
        'short_title_en': 'Warehouses & Purchasing',
        'description': 'الأصناف وحركة المخزون وطلبات الشراء وتقارير المخازن',
        'description_en': 'Items, stock movements, purchase orders, and warehouse reports',
        'color': '#1fb87a',
        'links': (
            ('الأصناف', 'Inventory Items', '/inventory', 'inventory.read'),
            ('حركة المخزن', 'Stock Movements', '/stock-movements', 'stock_movements.read'),
            ('طلبات الشراء', 'Purchase Orders', '/purchase-orders', 'purchase_orders.read'),
        ),
        'reports': (
            ('تقرير الأصناف', 'Inventory Report', '/reports/inventory', 'report_inventory.read'),
            ('تقرير حركة المخزن', 'Stock Movements Report', '/reports/stock-movements', 'report_stock.read'),
        ),
    },
    'personnel': {
        'title': 'منصة شؤون العاملين والفنيين',
        'title_en': 'Personnel & Technicians Platform',
        'short_title': 'شؤون العاملين',
        'short_title_en': 'Personnel Affairs',
        'description': 'الفنيون وفرق الصيانة ومتابعة الأداء الفني',
        'description_en': 'Technicians, maintenance teams, and field performance tracking',
        'color': '#8c6cff',
        'links': (
            ('الفنيون', 'Technicians', '/technicians', 'technicians.read'),
            ('فرق الصيانة', 'Maintenance Teams', '/technicians?tab=teams', 'technicians.read'),
        ),
        'reports': (
            ('تقرير الفنيين', 'Technicians Report', '/reports/technicians', 'report_technicians.read'),
        ),
    },
    'accounting': {
        'title': 'منصة الحسابات والمالية',
        'title_en': 'Accounting & Finance Platform',
        'short_title': 'الحسابات والمالية',
        'short_title_en': 'Accounting & Finance',
        'description': 'الإيرادات والمصروفات والفواتير والحسابات والقيود',
        'description_en': 'Revenues, expenses, invoices, accounts, and journal entries',
        'color': '#e09030',
        'links': (
            ('الإيرادات والتحصيل', 'Revenues & Collection', '/revenues', 'revenues.read'),
            ('المصروفات', 'Expenses', '/expenses', 'expenses.read'),
            ('الفواتير', 'Invoices', '/invoices', 'invoices.read'),
            ('شجرة الحسابات', 'Chart of Accounts', '/accounts', 'revenues.read'),
            ('القيود اليومية', 'Journal Entries', '/journals', 'revenues.read'),
            ('دفتر الأستاذ', 'General Ledger', '/ledger', 'revenues.read'),
            ('ميزان المراجعة', 'Trial Balance', '/trial-balance', 'revenues.read'),
            ('قائمة الدخل', 'Income Statement', '/pnl', 'revenues.read'),
            ('المركز المالي', 'Balance Sheet', '/balance-sheet', 'revenues.read'),
        ),
        'reports': (
            ('التقرير المالي', 'Financial Report', '/reports/financial', 'report_financial.read'),
            ('الصحة المالية', 'Financial Health', '/reports/financial-health', 'report_financial_health.read'),
            ('توقعات التحصيل', 'Collection Forecast', '/reports/contract-forecast', 'report_contract_forecast.read'),
            ('كشف حساب عميل', 'Customer Statement', '/reports/customer-statement', 'report_customer_statement.read'),
            ('تقرير الإيرادات', 'Revenues Report', '/reports/revenues', 'report_revenues.read'),
            ('تقرير المصروفات', 'Expenses Report', '/reports/expenses', 'report_expenses.read'),
            ('تقرير الفواتير', 'Invoices Report', '/reports/invoices', 'report_invoices.read'),
        ),
    },
    'management': {
        'title': 'منصة الإدارة والمتابعة',
        'title_en': 'Management & Oversight Platform',
        'short_title': 'الإدارة والمتابعة',
        'short_title_en': 'Management & Oversight',
        'description': 'لوحة المؤشرات والتقارير العامة وإعدادات النظام',
        'description_en': 'KPI dashboard, general reports, and system settings',
        'color': '#e04f6f',
        'links': (
            ('لوحة المؤشرات العامة', 'Main KPI Dashboard', '/dashboard', 'dashboard.read'),
            ('كل التقارير', 'All Reports', '/reports', 'reports_home.read'),
            ('إعدادات الحساب والنظام', 'Account & System Settings', '/settings', 'dashboard.read'),
        ),
        'reports': (
            ('تقرير الداشبورد', 'Dashboard Report', '/reports/dashboard', 'report_dashboard.read'),
            ('التقرير السنوي للعميل', 'Client Annual Report', '/reports/client-annual', 'report_client_annual.read'),
        ),
    },
}


def _pick_lang(lang: str) -> str:
    return 'en' if lang == 'en' else 'ar'


def portal_ui(lang: str = 'ar') -> dict:
    return PORTAL_UI[_pick_lang(lang)]


def home_ui(lang: str = 'ar') -> dict:
    return HOME_UI[_pick_lang(lang)]


def _localize_portal(portal: dict, lang: str) -> dict:
    if _pick_lang(lang) != 'en':
        return portal
    localized = dict(portal)
    localized['title'] = portal.get('title_en') or portal['title']
    localized['short_title'] = portal.get('short_title_en') or portal['short_title']
    localized['description'] = portal.get('description_en') or portal['description']
    for group in ('links', 'reports'):
        localized[group] = [
            {**item, 'label': item.get('label_en') or item['label']}
            for item in portal[group]
        ]
    return localized


def visible_department_portals(*, permission_ok, install_enabled, lang: str = 'ar'):
    """فلترة المنصات وروابطها وفق صلاحيات المستخدم والباقة."""
    visible = []
    for slug, definition in DEPARTMENT_PORTALS.items():
        portal = dict(definition)
        portal['slug'] = slug
        for group in ('links', 'reports'):
            allowed = []
            for item in definition[group]:
                label_ar, label_en, href, permission, *flags = item
                install_only = bool(flags and flags[0])
                if install_only and not install_enabled:
                    continue
                if permission_ok(permission):
                    separator = '&' if '?' in href else '?'
                    allowed.append({
                        'label': label_ar,
                        'label_en': label_en,
                        'href': f'{href}{separator}department={slug}',
                    })
            portal[group] = allowed
        if portal['links'] or portal['reports']:
            visible.append(_localize_portal(portal, lang))
    return visible
