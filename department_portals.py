"""منصات الأقسام — تعريفات /home و /departments/<slug>."""

from __future__ import annotations

HOME_UI = {
    'ar': {
        'page_title': 'منصات العمل',
        'kicker': 'اختر القسم',
        'title': 'منصات LiftCore',
        'subtitle': 'كل قسم له عملاؤه وعقوده وعملياته في مكان واحد — والتقارير في قسم مستقل.',
        'enter': 'دخول المنصة ←',
        'empty': 'لا توجد منصات متاحة لصلاحيات حسابك.',
    },
    'en': {
        'page_title': 'Work Platforms',
        'kicker': 'Choose a department',
        'title': 'LiftCore Platforms',
        'subtitle': 'Each department has its clients, contracts, and operations in one place — reports live in a dedicated section.',
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
        'groups_title': 'أقسام التقارير',
        'groups_count': '{n} أقسام',
        'hub_link': 'مركز التقارير',
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
        'groups_title': 'Report categories',
        'groups_count': '{n} categories',
        'hub_link': 'Reports hub',
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
        'reports': (),
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
            ('عقود التركيبات والتحديث', 'Installation Contracts', '/installation/contracts', 'contracts.read'),
            ('مشروعات التركيبات', 'Installation Projects', '/installation/projects', 'installation_projects.read', True),
            ('لوحة تنفيذ المشروعات', 'Project Execution Board', '/installation/', 'installation_projects.read', True),
        ),
        'reports': (),
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
            ('عرض سعر تحديث', 'Modernization Quote', '/sales/install/quotes/new?go=1&quote_kind=upgrade', 'installation_projects.read', True),
            ('إضافة أدوار', 'Add Floors Quote', '/sales/install/quotes/new?go=1&quote_kind=extend', 'installation_projects.read', True),
            ('عروض التركيب', 'Installation Quotes', '/sales/quotes?kind=install', 'installation_projects.read', True),
            ('عرض صيانة جديد', 'New Maintenance Quote', '/sales/maintenance-quotes/new', 'sales_quotes.read'),
            ('عروض الصيانة', 'Maintenance Quotes', '/sales/maintenance-quotes', 'sales_quotes.read'),
            ('تقدير تكلفة مصعد', 'Elevator Cost Estimate', '/elevator-estimates', 'elevator_estimates.read'),
            ('فرص البيع', 'Sales Leads', '/installation/leads', 'installation_projects.read', True),
        ),
        'reports': (),
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
        'reports': (),
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
            ('الموظفون', 'Employees', '/attendance/employees', 'attendance.read'),
            ('حضور اليوم', 'Today Attendance', '/attendance/today', 'attendance.read'),
            ('أجهزة البصمة', 'Biometric Devices', '/attendance/devices', 'attendance.read'),
            ('الفنيون', 'Technicians', '/technicians', 'technicians.read'),
            ('فرق الصيانة', 'Maintenance Teams', '/technicians?tab=teams', 'technicians.read'),
        ),
        'reports': (
            ('تقرير الحضور الشهري', 'Monthly Attendance', '/attendance/monthly', 'report_attendance.read'),
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
        'reports': (),
    },
    'reports': {
        'title': 'منصة التقارير والتحليل',
        'title_en': 'Reports & Analytics Platform',
        'short_title': 'التقارير',
        'short_title_en': 'Reports',
        'description': 'تقارير الشركة مقسّمة حسب الأقسام — صيانة، مالية، مخازن، وإدارة',
        'description_en': 'Company reports by category — maintenance, finance, inventory, and management',
        'color': '#5b7cfa',
        'links': (
            ('مركز التقارير', 'Reports Hub', '/reports', 'reports_home.read'),
        ),
        'report_groups': (
            {
                'slug': 'management',
                'title': 'تقارير إدارية',
                'title_en': 'Management Reports',
                'color': '#5b7cfa',
                'items': (
                    ('تقرير الداشبورد', 'Dashboard Report', '/reports/dashboard', 'report_dashboard.read'),
                    ('التقرير السنوي للعميل', 'Client Annual Report', '/reports/client-annual', 'report_client_annual.read'),
                ),
            },
            {
                'slug': 'clients',
                'title': 'العملاء والعقود',
                'title_en': 'Clients & Contracts',
                'color': '#7c6fff',
                'items': (
                    ('تقرير العملاء', 'Clients Report', '/reports/clients', 'report_clients.read'),
                    ('تقرير المصاعد', 'Elevators Report', '/reports/elevators', 'report_elevators.read'),
                    ('تقرير العقود', 'Contracts Report', '/reports/contracts', 'report_contracts.read'),
                ),
            },
            {
                'slug': 'maintenance',
                'title': 'الصيانة والأعطال',
                'title_en': 'Maintenance & Faults',
                'color': '#2a7fff',
                'items': (
                    ('تقرير زيارات الصيانة', 'Maintenance Visits Report', '/reports/maintenance-visits', 'report_maintenance.read'),
                    ('تقرير الأعطال', 'Faults Report', '/reports/faults', 'report_faults.read'),
                    ('تقرير قطع الغيار', 'Parts Billing Report', '/reports/parts-billing', 'parts_billing.read'),
                ),
            },
            {
                'slug': 'personnel',
                'title': 'الفنيين والأداء',
                'title_en': 'Technicians & Performance',
                'color': '#8c6cff',
                'items': (
                    ('تقرير الفنيين', 'Technicians Report', '/reports/technicians', 'report_technicians.read'),
                ),
            },
            {
                'slug': 'finance',
                'title': 'المالية والتحليل',
                'title_en': 'Finance & Analysis',
                'color': '#e09030',
                'items': (
                    ('التقرير المالي', 'Financial Report', '/reports/financial', 'report_financial.read'),
                    ('الصحة المالية', 'Financial Health', '/reports/financial-health', 'report_financial_health.read'),
                    ('توقعات التحصيل', 'Collection Forecast', '/reports/contract-forecast', 'report_contract_forecast.read'),
                    ('كشف حساب عميل', 'Customer Statement', '/reports/customer-statement', 'report_customer_statement.read'),
                    ('ربحية عميل', 'Customer Profitability', '/reports/customer-profitability', 'report_customer_profitability.read'),
                    ('تقرير الإيرادات', 'Revenues Report', '/reports/revenues', 'report_revenues.read'),
                    ('تقرير المصروفات', 'Expenses Report', '/reports/expenses', 'report_expenses.read'),
                    ('تقرير الفواتير', 'Invoices Report', '/reports/invoices', 'report_invoices.read'),
                ),
            },
            {
                'slug': 'inventory',
                'title': 'المخازن والمشتريات',
                'title_en': 'Inventory & Purchasing',
                'color': '#1fb87a',
                'items': (
                    ('تقرير الأصناف', 'Inventory Report', '/reports/inventory', 'report_inventory.read'),
                    ('تقرير حركة المخزن', 'Stock Movements Report', '/reports/stock-movements', 'report_stock.read'),
                ),
            },
        ),
        'reports': (),
    },
    'management': {
        'title': 'منصة الإدارة والمتابعة',
        'title_en': 'Management & Oversight Platform',
        'short_title': 'الإدارة والمتابعة',
        'short_title_en': 'Management & Oversight',
        'description': 'لوحة المؤشرات وإعدادات النظام',
        'description_en': 'KPI dashboard and system settings',
        'color': '#e04f6f',
        'links': (
            ('لوحة المؤشرات العامة', 'Main KPI Dashboard', '/dashboard', 'dashboard.read'),
            ('إعدادات الحساب والنظام', 'Account & System Settings', '/settings', 'dashboard.read'),
        ),
        'reports': (),
    },
}


def _pick_lang(lang: str) -> str:
    return 'en' if lang == 'en' else 'ar'


def portal_ui(lang: str = 'ar') -> dict:
    return PORTAL_UI[_pick_lang(lang)]


def home_ui(lang: str = 'ar') -> dict:
    return HOME_UI[_pick_lang(lang)]


def _filter_portal_items(
    items,
    *,
    slug: str,
    permission_ok,
    install_enabled,
    feature_ok,
):
    allowed = []
    for item in items:
        label_ar, label_en, href, permission, *flags = item
        install_only = bool(flags and flags[0])
        if install_only and not install_enabled:
            continue
        if href.startswith('/inventory') or href.startswith('/stock-movements') or href.startswith('/reports/inventory') or href.startswith('/reports/stock-movements'):
            if not feature_ok('inventory'):
                continue
        if href.startswith('/purchase-orders'):
            if not feature_ok('purchasing'):
                continue
        if permission_ok(permission):
            separator = '&' if '?' in href else '?'
            allowed.append({
                'label': label_ar,
                'label_en': label_en,
                'href': f'{href}{separator}department={slug}',
            })
    return allowed


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
    if portal.get('report_groups'):
        localized['report_groups'] = [
            {
                **grp,
                'title': grp.get('title_en') or grp['title'],
                'items': [
                    {**item, 'label': item.get('label_en') or item['label']}
                    for item in grp['items']
                ],
            }
            for grp in portal['report_groups']
        ]
    return localized


DEPARTMENT_REQUIRED_FEATURES = {
    'maintenance': 'maintenance_core',
    'installations': 'installation',
    'marketing': 'maintenance_core',
    'personnel': 'maintenance_core',
    'accounting': 'advanced_finance',
}


def visible_department_portals(
    *,
    permission_ok,
    install_enabled,
    feature_ok=None,
    lang: str = 'ar',
):
    """فلترة المنصات وروابطها وفق صلاحيات المستخدم والباقة."""
    if feature_ok is None:
        feature_ok = lambda _key: True

    visible = []
    for slug, definition in DEPARTMENT_PORTALS.items():
        required = DEPARTMENT_REQUIRED_FEATURES.get(slug)
        if required and not feature_ok(required):
            continue
        if slug == 'inventory' and not feature_ok('inventory') and not feature_ok('purchasing'):
            continue

        portal = dict(definition)
        portal['slug'] = slug
        portal['report_groups'] = []
        for group in ('links', 'reports'):
            portal[group] = _filter_portal_items(
                definition.get(group, ()),
                slug=slug,
                permission_ok=permission_ok,
                install_enabled=install_enabled,
                feature_ok=feature_ok,
            )
        for group_def in definition.get('report_groups', ()):
            items = _filter_portal_items(
                group_def.get('items', ()),
                slug=slug,
                permission_ok=permission_ok,
                install_enabled=install_enabled,
                feature_ok=feature_ok,
            )
            if not items:
                continue
            portal['report_groups'].append({
                'slug': group_def['slug'],
                'title': group_def['title'],
                'title_en': group_def.get('title_en', group_def['title']),
                'color': group_def.get('color', definition.get('color', '#5b7cfa')),
                'items': items,
            })
        if portal['links'] or portal['reports'] or portal['report_groups']:
            visible.append(_localize_portal(portal, lang))
    return visible


def _portal_href_entries():
    """(slug, raw_href) لكل رابط في تعريفات المنصات."""
    out = []
    for slug, definition in DEPARTMENT_PORTALS.items():
        for group in ('links', 'reports'):
            for item in definition.get(group, ()):
                out.append((slug, item[2]))
        for group_def in definition.get('report_groups', ()):
            for item in group_def.get('items', ()):
                out.append((slug, item[2]))
    return out


def resolve_report_group_slug(path: str, args) -> str | None:
    """تحديد مجموعة التقارير النشطة من المسار الحالي."""
    req_path = (path or '/').rstrip('/') or '/'
    if req_path == '/reports':
        return None
    if not req_path.startswith('/reports/'):
        return None
    reports_def = DEPARTMENT_PORTALS.get('reports', {})
    for group_def in reports_def.get('report_groups', ()):
        for item in group_def.get('items', ()):
            href_path, _href_q = _parse_href(item[2])
            if href_path == req_path:
                return group_def['slug']
    return None


def _parse_href(href: str) -> tuple[str, dict[str, str]]:
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(href or '')
    path = (parsed.path or '/').rstrip('/') or '/'
    query = {}
    for key, vals in parse_qs(parsed.query, keep_blank_values=True).items():
        if vals:
            query[key] = vals[0]
    return path, query


def _request_query_map(args) -> dict[str, str]:
    if not args:
        return {}
    try:
        return {k: (args.get(k) or '') for k in args.keys()}
    except Exception:
        return {}


def department_href_is_active(href: str, path: str, args) -> bool:
    """هل الرابط الحالي يطابق تبويب القسم؟"""
    href_path, href_q = _parse_href(href)
    req_path = (path or '/').rstrip('/') or '/'
    if href_path != req_path:
        return False
    req_q = _request_query_map(args)
    for key, value in href_q.items():
        if key == 'department':
            continue
        if str(req_q.get(key, '')) != str(value):
            return False
    return True


def resolve_department_slug(path: str, args, session_slug: str | None = None) -> str | None:
    """تحديد منصة القسم من ?department= أو من مسار الصفحة أو الجلسة."""
    explicit = (args.get('department') if args else '') or ''
    explicit = str(explicit).strip()
    if explicit in DEPARTMENT_PORTALS:
        return explicit

    req_path = (path or '/').rstrip('/') or '/'
    if req_path == '/reports' or req_path.startswith('/reports/'):
        return 'reports'

    if req_path.startswith('/departments/'):
        parts = [p for p in req_path.split('/') if p]
        if len(parts) >= 2 and parts[1] in DEPARTMENT_PORTALS:
            return parts[1]

    req_q = _request_query_map(args)
    candidates: list[tuple[int, str]] = []

    for slug, href in _portal_href_entries():
        href_path, href_q = _parse_href(href)
        if href_path != req_path:
            continue
        ok = True
        for key, value in href_q.items():
            if str(req_q.get(key, '')) != str(value):
                ok = False
                break
        if not ok:
            continue
        if not href_q and any(k in req_q for k in ('scope', 'kind', 'tab')):
            continue
        candidates.append((len(href_q), slug))

    if not candidates:
        sess = (session_slug or '').strip()
        return sess if sess in DEPARTMENT_PORTALS else None

    candidates.sort(key=lambda x: (-x[0], x[1]))
    slugs = [slug for _, slug in candidates]
    if len(slugs) == 1:
        return slugs[0]
    sess = (session_slug or '').strip()
    if sess in slugs:
        return sess
    return slugs[0]
