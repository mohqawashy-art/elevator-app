"""
LiftCore — صلاحيات اختيارية فوق الأدوار (admin / manager / viewer).

عند تعطيل النظام (الافتراضي): السلوك كما كان — أدوار فقط.
عند التفعيل من الإعدادات: يمكن منح/حجب صلاحيات لكل مستخدم.
"""

from __future__ import annotations

import json
import os
from typing import Any

from liftcore_rbac import ROLE_ADMIN, ROLE_MANAGER, ROLE_VIEWER

# ── مفاتيح الصلاحيات ──────────────────────────────────────────────

PERMISSION_DEFS: tuple[dict[str, str], ...] = (
    {'key': 'dashboard.read', 'label_ar': 'لوحة التحكم', 'label_en': 'Dashboard', 'group_ar': 'عام'},
    {'key': 'clients.read', 'label_ar': 'عرض العملاء والعقود', 'label_en': 'View clients', 'group_ar': 'العملاء'},
    {'key': 'clients.write', 'label_ar': 'تعديل العملاء والعقود', 'label_en': 'Edit clients', 'group_ar': 'العملاء'},
    {'key': 'elevators.read', 'label_ar': 'عرض المصاعد', 'label_en': 'View elevators', 'group_ar': 'العملاء'},
    {'key': 'elevators.write', 'label_ar': 'تعديل المصاعد', 'label_en': 'Edit elevators', 'group_ar': 'العملاء'},
    {'key': 'technicians.read', 'label_ar': 'عرض الفنيين', 'label_en': 'View technicians', 'group_ar': 'الفريق'},
    {'key': 'technicians.write', 'label_ar': 'تعديل الفنيين', 'label_en': 'Edit technicians', 'group_ar': 'الفريق'},
    {'key': 'operations.read', 'label_ar': 'عرض الصيانة والأعطال', 'label_en': 'View operations', 'group_ar': 'العمليات'},
    {'key': 'operations.write', 'label_ar': 'تعديل الصيانة والأعطال', 'label_en': 'Edit operations', 'group_ar': 'العمليات'},
    {'key': 'installation.read', 'label_ar': 'عرض التركيب والتقديرات', 'label_en': 'View installation', 'group_ar': 'التركيب'},
    {'key': 'installation.write', 'label_ar': 'تعديل التركيب', 'label_en': 'Edit installation', 'group_ar': 'التركيب'},
    {'key': 'finance.read', 'label_ar': 'عرض المالية', 'label_en': 'View finance', 'group_ar': 'المالية'},
    {'key': 'finance.write', 'label_ar': 'تعديل المالية والفواتير', 'label_en': 'Edit finance', 'group_ar': 'المالية'},
    {'key': 'inventory.read', 'label_ar': 'عرض المخزن', 'label_en': 'View inventory', 'group_ar': 'المخزن'},
    {'key': 'inventory.write', 'label_ar': 'تعديل المخزن', 'label_en': 'Edit inventory', 'group_ar': 'المخزن'},
    {'key': 'reports.read', 'label_ar': 'التقارير', 'label_en': 'Reports', 'group_ar': 'التقارير'},
    {'key': 'settings.admin', 'label_ar': 'إعدادات النظام والمستخدمين', 'label_en': 'System settings', 'group_ar': 'الإدارة'},
    {'key': 'data.delete', 'label_ar': 'حذف السجلات', 'label_en': 'Delete records', 'group_ar': 'الإدارة'},
    {'key': 'billing.repair', 'label_ar': 'إصلاح فروقات الفوترة', 'label_en': 'Billing repair', 'group_ar': 'الإدارة'},
)

ALL_PERMISSION_KEYS = frozenset(p['key'] for p in PERMISSION_DEFS)

READ_PERMISSIONS = frozenset(k for k in ALL_PERMISSION_KEYS if k.endswith('.read'))
WRITE_PERMISSIONS = frozenset(k for k in ALL_PERMISSION_KEYS if k.endswith('.write') or k in (
    'settings.admin', 'data.delete', 'billing.repair',
))

ROLE_DEFAULT_PERMISSIONS: dict[str, frozenset[str]] = {
    ROLE_ADMIN: ALL_PERMISSION_KEYS,
    ROLE_MANAGER: frozenset(
        k for k in ALL_PERMISSION_KEYS
        if k not in ('settings.admin', 'data.delete', 'billing.repair')
    ),
    ROLE_VIEWER: frozenset(k for k in ALL_PERMISSION_KEYS if k.endswith('.read')),
}

# مسار → (صلاحية قراءة GET, صلاحية كتابة mutating)
PATH_RULES: tuple[tuple[str, str, str], ...] = (
    ('/dashboard', 'dashboard.read', 'dashboard.read'),
    ('/clients', 'clients.read', 'clients.write'),
    ('/elevators', 'elevators.read', 'elevators.write'),
    ('/contracts', 'clients.read', 'clients.write'),
    ('/technicians', 'technicians.read', 'technicians.write'),
    ('/maintenance-visits', 'operations.read', 'operations.write'),
    ('/faults', 'operations.read', 'operations.write'),
    ('/parts-billing', 'operations.read', 'operations.write'),
    ('/elevator-estimates', 'installation.read', 'installation.write'),
    ('/installation', 'installation.read', 'installation.write'),
    ('/revenues', 'finance.read', 'finance.write'),
    ('/expenses', 'finance.read', 'finance.write'),
    ('/invoices', 'finance.read', 'finance.write'),
    ('/inventory', 'inventory.read', 'inventory.write'),
    ('/stock-movements', 'inventory.read', 'inventory.write'),
    ('/purchase-orders', 'inventory.read', 'inventory.write'),
    ('/reports', 'reports.read', 'reports.read'),
    ('/settings', 'dashboard.read', 'settings.admin'),
    ('/api/admin/billing', 'billing.repair', 'billing.repair'),
    ('/api/reports/billing-discrepancies', 'finance.read', 'finance.read'),
)

ADMIN_ONLY_ENDPOINTS_PERMISSION = 'settings.admin'
DELETE_PERMISSION = 'data.delete'


def custom_permissions_enabled(settings=None) -> bool:
    if (os.environ.get('LIFTCORE_CUSTOM_PERMISSIONS') or '').strip() in ('1', 'true', 'yes', 'on'):
        return True
    if settings is not None and getattr(settings, 'custom_permissions_enabled', False):
        return True
    return False


def parse_permissions_extra(raw: str | None) -> dict[str, list[str]]:
    if not raw:
        return {'grants': [], 'denies': []}
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {'grants': [], 'denies': []}
    if not isinstance(data, dict):
        return {'grants': [], 'denies': []}
    grants = [g for g in (data.get('grants') or []) if g in ALL_PERMISSION_KEYS]
    denies = [d for d in (data.get('denies') or []) if d in ALL_PERMISSION_KEYS]
    return {'grants': grants, 'denies': denies}


def dump_permissions_extra(grants: list[str], denies: list[str]) -> str:
    grants = [g for g in grants if g in ALL_PERMISSION_KEYS]
    denies = [d for d in denies if d in ALL_PERMISSION_KEYS]
    return json.dumps({'grants': grants, 'denies': denies}, ensure_ascii=False)


def role_default_permissions(role: str | None) -> frozenset[str]:
    return ROLE_DEFAULT_PERMISSIONS.get(role or ROLE_VIEWER, ROLE_DEFAULT_PERMISSIONS[ROLE_VIEWER])


def effective_permissions(user, settings=None) -> frozenset[str]:
    if not user:
        return frozenset()
    role = user.role or ROLE_VIEWER
    if role == ROLE_ADMIN and not custom_permissions_enabled(settings):
        return ALL_PERMISSION_KEYS
    base = set(role_default_permissions(role))
    if not custom_permissions_enabled(settings):
        return frozenset(base)
    if role == ROLE_ADMIN:
        # مدير النظام يبقى كاملاً — التخصيص لباقي الأدوار
        return ALL_PERMISSION_KEYS
    extra = parse_permissions_extra(getattr(user, 'permissions_extra', None))
    return frozenset((base | set(extra['grants'])) - set(extra['denies']))


def user_has_permission(user, perm: str, settings=None) -> bool:
    if not user or perm not in ALL_PERMISSION_KEYS:
        return False
    return perm in effective_permissions(user, settings)


def user_can_write_module(user, settings=None) -> bool:
    """هل للمستخدم أي صلاحية كتابة فعّالة؟"""
    if not user:
        return False
    if not custom_permissions_enabled(settings):
        return user.role in (ROLE_ADMIN, ROLE_MANAGER)
    perms = effective_permissions(user, settings)
    return bool(perms & WRITE_PERMISSIONS)


def permissions_for_path(path: str, method: str) -> tuple[str | None, str | None]:
    path = path or ''
    for prefix, read_p, write_p in PATH_RULES:
        if path == prefix or path.startswith(prefix + '/'):
            if method.upper() in {'POST', 'PUT', 'PATCH', 'DELETE'}:
                return read_p, write_p
            return read_p, read_p
    return None, None


def check_path_permission(user, *, path: str, method: str, settings=None) -> str | None:
    """
    يرجع مفتاح الصلاحية الناقصة أو None إذا مسموح.
    """
    if not user or not custom_permissions_enabled(settings):
        return None
    if user.role == ROLE_ADMIN:
        return None
    read_p, write_p = permissions_for_path(path, method)
    if not read_p:
        return None
    need = write_p if method.upper() in {'POST', 'PUT', 'PATCH', 'DELETE'} else read_p
    if need and not user_has_permission(user, need, settings):
        return need
    return None


def permission_groups_for_ui() -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = {}
    order: list[str] = []
    for p in PERMISSION_DEFS:
        g = p['group_ar']
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(p)
    return [{'group_ar': g, 'items': groups[g]} for g in order]


def permissions_from_form(form) -> tuple[list[str], list[str]]:
    grants = form.getlist('perm_grant')
    denies = form.getlist('perm_deny')
    return (
        [g for g in grants if g in ALL_PERMISSION_KEYS],
        [d for d in denies if d in ALL_PERMISSION_KEYS],
    )


PERMISSION_SCHEMA_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    'settings': (('custom_permissions_enabled', 'BOOLEAN'),),
    'users': (('permissions_extra', 'TEXT'),),
}


def ensure_permissions_schema(db_session, engine) -> bool:
    """يضيف أعمدة الصلاحيات الاختيارية إن نُقصت (SQLite / PostgreSQL)."""
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
