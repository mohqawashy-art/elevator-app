"""LiftCore — صلاحيات الدور «مخصص» على مستوى الصفحات."""

from __future__ import annotations

import json
from typing import Any

from liftcore_rbac import ROLE_ADMIN, ROLE_CUSTOM, ROLE_MANAGER, ROLE_VIEWER

PERM_READ = 'read'
PERM_CREATE = 'create'
PERM_EDIT = 'edit'
PERM_ACTIONS = (PERM_READ, PERM_CREATE, PERM_EDIT)

PAGE_DEFS: tuple[dict[str, str], ...] = (
    {'slug': 'dashboard', 'label_ar': 'لوحة التحكم', 'label_en': 'Dashboard', 'group_ar': 'عام'},
    {'slug': 'clients', 'label_ar': 'العملاء', 'label_en': 'Clients', 'group_ar': 'العملاء'},
    {'slug': 'contracts', 'label_ar': 'العقود', 'label_en': 'Contracts', 'group_ar': 'العملاء'},
    {'slug': 'elevators', 'label_ar': 'المصاعد', 'label_en': 'Elevators', 'group_ar': 'العملاء'},
    {'slug': 'technicians', 'label_ar': 'الفنيون', 'label_en': 'Technicians', 'group_ar': 'الفريق'},
    {'slug': 'maintenance_visits', 'label_ar': 'زيارات الصيانة', 'label_en': 'Maintenance Visits', 'group_ar': 'العمليات'},
    {'slug': 'faults', 'label_ar': 'الأعطال', 'label_en': 'Faults', 'group_ar': 'العمليات'},
    {'slug': 'whatsapp_inbox', 'label_ar': 'وارد واتساب', 'label_en': 'WhatsApp Inbox', 'group_ar': 'العمليات'},
    {'slug': 'parts_billing', 'label_ar': 'تركيب قطع الغيار', 'label_en': 'Parts Billing', 'group_ar': 'العمليات'},
    {'slug': 'elevator_estimates', 'label_ar': 'تقدير تكلفة مصعد', 'label_en': 'Elevator Estimates', 'group_ar': 'التركيب'},
    {'slug': 'installation_projects', 'label_ar': 'مشاريع التركيب', 'label_en': 'Installation Projects', 'group_ar': 'التركيب'},
    {'slug': 'revenues', 'label_ar': 'الإيرادات', 'label_en': 'Revenues', 'group_ar': 'المالية'},
    {'slug': 'expenses', 'label_ar': 'المصروفات', 'label_en': 'Expenses', 'group_ar': 'المالية'},
    {'slug': 'invoices', 'label_ar': 'الفواتير', 'label_en': 'Invoices', 'group_ar': 'المالية'},
    {'slug': 'inventory', 'label_ar': 'الأصناف', 'label_en': 'Inventory', 'group_ar': 'المخزن'},
    {'slug': 'stock_movements', 'label_ar': 'حركة المخزن', 'label_en': 'Stock Movements', 'group_ar': 'المخزن'},
    {'slug': 'purchase_orders', 'label_ar': 'طلبات الشراء', 'label_en': 'Purchase Orders', 'group_ar': 'المخزن'},
    {'slug': 'reports_home', 'label_ar': 'كل التقارير', 'label_en': 'All Reports', 'group_ar': 'التقارير'},
    {'slug': 'report_dashboard', 'label_ar': 'تقرير الداشبورد', 'label_en': 'Dashboard Report', 'group_ar': 'التقارير'},
    {'slug': 'report_client_annual', 'label_ar': 'التقرير السنوي للعميل', 'label_en': 'Client Annual Report', 'group_ar': 'التقارير'},
    {'slug': 'report_clients', 'label_ar': 'تقرير العملاء', 'label_en': 'Clients Report', 'group_ar': 'التقارير'},
    {'slug': 'report_elevators', 'label_ar': 'تقرير المصاعد', 'label_en': 'Elevators Report', 'group_ar': 'التقارير'},
    {'slug': 'report_contracts', 'label_ar': 'تقرير العقود', 'label_en': 'Contracts Report', 'group_ar': 'التقارير'},
    {'slug': 'report_technicians', 'label_ar': 'تقرير الفنيين', 'label_en': 'Technicians Report', 'group_ar': 'التقارير'},
    {'slug': 'report_maintenance', 'label_ar': 'تقرير زيارات الصيانة', 'label_en': 'Maintenance Report', 'group_ar': 'التقارير'},
    {'slug': 'report_faults', 'label_ar': 'تقرير الأعطال', 'label_en': 'Faults Report', 'group_ar': 'التقارير'},
    {'slug': 'report_financial', 'label_ar': 'التقرير المالي', 'label_en': 'Financial Report', 'group_ar': 'التقارير'},
    {'slug': 'report_contract_forecast', 'label_ar': 'توقعات تحصيل العقود', 'label_en': 'Contract Forecast', 'group_ar': 'التقارير'},
    {'slug': 'report_financial_health', 'label_ar': 'الصحة المالية', 'label_en': 'Financial Health', 'group_ar': 'التقارير'},
    {'slug': 'report_revenues', 'label_ar': 'تقرير الإيرادات', 'label_en': 'Revenues Report', 'group_ar': 'التقارير'},
    {'slug': 'report_expenses', 'label_ar': 'تقرير المصروفات', 'label_en': 'Expenses Report', 'group_ar': 'التقارير'},
    {'slug': 'report_invoices', 'label_ar': 'تقرير الفواتير', 'label_en': 'Invoices Report', 'group_ar': 'التقارير'},
    {'slug': 'report_customer_statement', 'label_ar': 'كشف حساب عميل', 'label_en': 'Customer Statement', 'group_ar': 'التقارير'},
    {'slug': 'report_inventory', 'label_ar': 'تقرير الأصناف', 'label_en': 'Inventory Report', 'group_ar': 'التقارير'},
    {'slug': 'report_stock', 'label_ar': 'تقرير حركة المخزن', 'label_en': 'Stock Movement Report', 'group_ar': 'التقارير'},
)


def page_perm(slug: str, action: str) -> str:
    return f'{slug}.{action}'


PERMISSION_DEFS: tuple[dict[str, str], ...] = tuple(
    {
        'key': page_perm(page['slug'], action),
        'label_ar': page['label_ar'],
        'label_en': page['label_en'],
        'group_ar': page['group_ar'],
        'action': action,
    }
    for page in PAGE_DEFS
    for action in PERM_ACTIONS
)

PAGE_SLUGS = frozenset(page['slug'] for page in PAGE_DEFS)
CUSTOM_ROLE_PERMISSION_KEYS = frozenset(p['key'] for p in PERMISSION_DEFS)

ADMIN_ONLY_PERMISSION_KEYS = frozenset({
    'settings.admin', 'data.delete', 'billing.repair',
})
ALL_PERMISSION_KEYS = CUSTOM_ROLE_PERMISSION_KEYS | ADMIN_ONLY_PERMISSION_KEYS

WRITE_PERMISSIONS = frozenset(
    k for k in CUSTOM_ROLE_PERMISSION_KEYS
    if k.endswith(f'.{PERM_CREATE}') or k.endswith(f'.{PERM_EDIT}')
) | ADMIN_ONLY_PERMISSION_KEYS

ROLE_DEFAULT_PERMISSIONS: dict[str, frozenset[str]] = {
    ROLE_ADMIN: ALL_PERMISSION_KEYS,
    ROLE_MANAGER: frozenset(CUSTOM_ROLE_PERMISSION_KEYS),
    ROLE_VIEWER: frozenset(
        k for k in CUSTOM_ROLE_PERMISSION_KEYS if k.endswith(f'.{PERM_READ}')
    ),
    ROLE_CUSTOM: frozenset(),
}

LEGACY_GRANT_MAP: dict[str, tuple[str, ...]] = {
    'dashboard.read': (page_perm('dashboard', PERM_READ),),
    'clients.read': (
        page_perm('clients', PERM_READ),
        page_perm('contracts', PERM_READ),
    ),
    'clients.write': (
        page_perm('clients', PERM_CREATE), page_perm('clients', PERM_EDIT),
        page_perm('contracts', PERM_CREATE), page_perm('contracts', PERM_EDIT),
    ),
    'elevators.read': (page_perm('elevators', PERM_READ),),
    'elevators.write': (
        page_perm('elevators', PERM_CREATE), page_perm('elevators', PERM_EDIT),
    ),
    'technicians.read': (page_perm('technicians', PERM_READ),),
    'technicians.write': (
        page_perm('technicians', PERM_CREATE), page_perm('technicians', PERM_EDIT),
    ),
    'operations.read': (
        page_perm('maintenance_visits', PERM_READ),
        page_perm('faults', PERM_READ),
        page_perm('whatsapp_inbox', PERM_READ),
        page_perm('parts_billing', PERM_READ),
    ),
    'operations.write': (
        page_perm('maintenance_visits', PERM_CREATE), page_perm('maintenance_visits', PERM_EDIT),
        page_perm('faults', PERM_CREATE), page_perm('faults', PERM_EDIT),
        page_perm('whatsapp_inbox', PERM_CREATE), page_perm('whatsapp_inbox', PERM_EDIT),
        page_perm('parts_billing', PERM_CREATE), page_perm('parts_billing', PERM_EDIT),
    ),
    'installation.read': (
        page_perm('elevator_estimates', PERM_READ),
        page_perm('installation_projects', PERM_READ),
    ),
    'installation.write': (
        page_perm('elevator_estimates', PERM_CREATE), page_perm('elevator_estimates', PERM_EDIT),
        page_perm('installation_projects', PERM_CREATE), page_perm('installation_projects', PERM_EDIT),
    ),
    'finance.read': (
        page_perm('revenues', PERM_READ),
        page_perm('expenses', PERM_READ),
        page_perm('invoices', PERM_READ),
    ),
    'finance.write': (
        page_perm('revenues', PERM_CREATE), page_perm('revenues', PERM_EDIT),
        page_perm('expenses', PERM_CREATE), page_perm('expenses', PERM_EDIT),
        page_perm('invoices', PERM_CREATE), page_perm('invoices', PERM_EDIT),
    ),
    'inventory.read': (
        page_perm('inventory', PERM_READ),
        page_perm('stock_movements', PERM_READ),
        page_perm('purchase_orders', PERM_READ),
    ),
    'inventory.write': (
        page_perm('inventory', PERM_CREATE), page_perm('inventory', PERM_EDIT),
        page_perm('stock_movements', PERM_CREATE), page_perm('stock_movements', PERM_EDIT),
        page_perm('purchase_orders', PERM_CREATE), page_perm('purchase_orders', PERM_EDIT),
    ),
    'reports.read': tuple(page_perm(page['slug'], PERM_READ) for page in PAGE_DEFS if page['group_ar'] == 'التقارير'),
}

ADMIN_ONLY_ENDPOINTS_PERMISSION = 'settings.admin'

SELF_SERVICE_SETTINGS_PREFIXES = (
    '/settings/profile',
    '/settings/theme',
    '/settings/password',
)

PATH_PAGE_RULES: tuple[tuple[str, str], ...] = (
    ('/settings/users', 'dashboard'),
    ('/settings/profile', 'dashboard'),
    ('/settings/theme', 'dashboard'),
    ('/settings/password', 'dashboard'),
    ('/dashboard', 'dashboard'),
    ('/clients', 'clients'),
    ('/api/customers', 'clients'),
    ('/contracts', 'contracts'),
    ('/elevators', 'elevators'),
    ('/api/elevators', 'elevators'),
    ('/technicians', 'technicians'),
    ('/api/technicians', 'technicians'),
    ('/maintenance-visits', 'maintenance_visits'),
    ('/api/maintenance', 'maintenance_visits'),
    ('/faults', 'faults'),
    ('/api/faults', 'faults'),
    ('/support/whatsapp', 'whatsapp_inbox'),
    ('/parts-billing', 'parts_billing'),
    ('/api/parts-billing', 'parts_billing'),
    ('/elevator-estimates', 'elevator_estimates'),
    ('/installation', 'installation_projects'),
    ('/api/revenues', 'revenues'),
    ('/revenues', 'revenues'),
    ('/accounts', 'revenues'),
    ('/journals', 'revenues'),
    ('/ledger', 'revenues'),
    ('/trial-balance', 'revenues'),
    ('/pnl', 'revenues'),
    ('/balance-sheet', 'revenues'),
    ('/expenses', 'expenses'),
    ('/invoices', 'invoices'),
    ('/inventory', 'inventory'),
    ('/stock-movements', 'stock_movements'),
    ('/purchase-orders', 'purchase_orders'),
    ('/reports/dashboard', 'report_dashboard'),
    ('/reports/client-annual', 'report_client_annual'),
    ('/reports/clients', 'report_clients'),
    ('/reports/elevators', 'report_elevators'),
    ('/reports/contracts', 'report_contracts'),
    ('/reports/technicians', 'report_technicians'),
    ('/reports/maintenance-visits', 'report_maintenance'),
    ('/reports/faults', 'report_faults'),
    ('/reports/financial', 'report_financial'),
    ('/reports/contract-forecast', 'report_contract_forecast'),
    ('/reports/financial-health', 'report_financial_health'),
    ('/reports/revenues', 'report_revenues'),
    ('/reports/expenses', 'report_expenses'),
    ('/reports/invoices', 'report_invoices'),
    ('/reports/customer-statement', 'report_customer_statement'),
    ('/reports/inventory', 'report_inventory'),
    ('/reports/stock-movements', 'report_stock'),
    ('/reports', 'reports_home'),
)


def _normalize_grants(grants: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for grant in grants:
        for g in LEGACY_GRANT_MAP.get(grant, (grant,)):
            if g in CUSTOM_ROLE_PERMISSION_KEYS and g not in seen:
                out.append(g)
                seen.add(g)
    return out


def _split_perm(perm: str) -> tuple[str | None, str | None]:
    if '.' not in perm:
        return None, None
    slug, action = perm.rsplit('.', 1)
    if slug not in PAGE_SLUGS or action not in PERM_ACTIONS:
        return None, None
    return slug, action


def _custom_has_permission(grants: frozenset[str], perm: str) -> bool:
    slug, action = _split_perm(perm)
    if not slug:
        return perm in grants
    if action == PERM_READ:
        return any(page_perm(slug, a) in grants for a in PERM_ACTIONS)
    if action == PERM_CREATE:
        return any(page_perm(slug, a) in grants for a in (PERM_CREATE, PERM_EDIT))
    return page_perm(slug, PERM_EDIT) in grants


def is_custom_role(user) -> bool:
    return bool(user and (user.role or '') == ROLE_CUSTOM)


def parse_permissions_extra(raw: str | None) -> dict[str, list[str]]:
    if not raw:
        return {'grants': [], 'denies': []}
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {'grants': [], 'denies': []}
    if not isinstance(data, dict):
        return {'grants': [], 'denies': []}
    return {'grants': _normalize_grants(list(data.get('grants') or [])), 'denies': []}


def dump_permissions_extra(grants: list[str]) -> str:
    return json.dumps({'grants': _normalize_grants(grants), 'denies': []}, ensure_ascii=False)


def role_default_permissions(role: str | None) -> frozenset[str]:
    return ROLE_DEFAULT_PERMISSIONS.get(role or ROLE_VIEWER, ROLE_DEFAULT_PERMISSIONS[ROLE_VIEWER])


def effective_permissions(user, settings=None) -> frozenset[str]:
    if not user:
        return frozenset()
    role = user.role or ROLE_VIEWER
    if role == ROLE_CUSTOM:
        extra = parse_permissions_extra(getattr(user, 'permissions_extra', None))
        return frozenset(extra['grants'])
    return role_default_permissions(role)


def user_has_permission(user, perm: str, settings=None) -> bool:
    if not user or perm not in ALL_PERMISSION_KEYS:
        return False
    perms = effective_permissions(user, settings)
    if user.role == ROLE_CUSTOM:
        return _custom_has_permission(perms, perm)
    return perm in perms


def user_can_write_module(user, settings=None) -> bool:
    if not user:
        return False
    if user.role in (ROLE_ADMIN, ROLE_MANAGER):
        return True
    if user.role == ROLE_CUSTOM:
        perms = effective_permissions(user, settings)
        return any(_custom_has_permission(perms, perm) for perm in WRITE_PERMISSIONS)
    return False


def permission_for_path(path: str, method: str) -> str | None:
    path = path or ''
    matched_slug = None
    matched_len = -1
    for prefix, slug in PATH_PAGE_RULES:
        if path == prefix or path.startswith(prefix + '/'):
            if len(prefix) > matched_len:
                matched_slug = slug
                matched_len = len(prefix)
    if not matched_slug:
        return None
    if method.upper() not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return page_perm(matched_slug, PERM_READ)
    if (
        path.endswith('/add')
        or '/add/' in path
        or path.endswith('/create')
        or '/create/' in path
        or '/import' in path
    ):
        return page_perm(matched_slug, PERM_CREATE)
    return page_perm(matched_slug, PERM_EDIT)


def check_path_permission(user, *, path: str, method: str, settings=None) -> str | None:
    if not is_custom_role(user):
        return None
    path = path or ''
    for prefix in SELF_SERVICE_SETTINGS_PREFIXES:
        if path == prefix or path.startswith(prefix + '/'):
            return None
    need = permission_for_path(path, method)
    if need and not user_has_permission(user, need, settings):
        return need
    return None


# أول مسار مناسب لكل slug (للتحويل بعد تسجيل الدخول / رفض الصلاحية)
PAGE_HOME_PATHS: dict[str, str] = {
    'dashboard': '/dashboard',
    'clients': '/clients',
    'contracts': '/contracts',
    'elevators': '/elevators',
    'technicians': '/technicians',
    'maintenance_visits': '/maintenance-visits',
    'faults': '/faults',
    'whatsapp_inbox': '/support/whatsapp',
    'parts_billing': '/parts-billing',
    'elevator_estimates': '/elevator-estimates',
    'installation_projects': '/installation',
    'revenues': '/revenues',
    'expenses': '/expenses',
    'invoices': '/invoices',
    'inventory': '/inventory',
    'stock_movements': '/stock-movements',
    'purchase_orders': '/purchase-orders',
    'reports_home': '/reports',
    'report_dashboard': '/reports/dashboard',
    'report_client_annual': '/reports/client-annual',
    'report_clients': '/reports/clients',
    'report_elevators': '/reports/elevators',
    'report_contracts': '/reports/contracts',
    'report_technicians': '/reports/technicians',
    'report_maintenance': '/reports/maintenance-visits',
    'report_faults': '/reports/faults',
    'report_financial': '/reports/financial',
    'report_contract_forecast': '/reports/contract-forecast',
    'report_financial_health': '/reports/financial-health',
    'report_revenues': '/reports/revenues',
    'report_expenses': '/reports/expenses',
    'report_invoices': '/reports/invoices',
    'report_customer_statement': '/reports/customer-statement',
    'report_inventory': '/reports/inventory',
    'report_stock': '/reports/stock-movements',
}


def first_allowed_path_for_user(user) -> str:
    """يرجع أول مسار يملك المستخدم قراءته، أو /dashboard."""
    if not user:
        return '/dashboard'
    if not is_custom_role(user):
        return '/dashboard'
    grants = effective_permissions(user)
    # لوحة التحكم دائماً متاحة كصفحة هبوط
    for page in PAGE_DEFS:
        slug = page['slug']
        if slug == 'dashboard':
            continue
        if any(page_perm(slug, a) in grants for a in PERM_ACTIONS):
            return PAGE_HOME_PATHS.get(slug, '/dashboard')
    return '/dashboard'


def permission_groups_for_ui() -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for page in PAGE_DEFS:
        group = page['group_ar']
        if group not in groups:
            groups[group] = []
            order.append(group)
        groups[group].append({
            'slug': page['slug'],
            'label_ar': page['label_ar'],
            'label_en': page['label_en'],
            'perms': {
                PERM_READ: page_perm(page['slug'], PERM_READ),
                PERM_CREATE: page_perm(page['slug'], PERM_CREATE),
                PERM_EDIT: page_perm(page['slug'], PERM_EDIT),
            },
        })
    return [{'group_ar': group, 'pages': groups[group]} for group in order]


def permissions_grants_from_form(form) -> list[str]:
    return _normalize_grants(form.getlist('perm_grant'))


PERMISSION_SCHEMA_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    'users': (('permissions_extra', 'TEXT'),),
}


def ensure_permissions_schema(db_session, engine) -> bool:
    from sqlalchemy import inspect, text

    changed = False
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    for table, cols in PERMISSION_SCHEMA_COLUMNS.items():
        if table not in tables:
            continue
        existing = {c['name'] for c in insp.get_columns(table)}
        for col_name, col_type in cols:
            if col_name in existing:
                continue
            db_session.execute(text(
                f'ALTER TABLE {table} ADD COLUMN {col_name} {col_type}'
            ))
            changed = True
    if changed:
        db_session.commit()
    return changed
