"""كتالوج باقات وإضافات LiftCore SaaS — مصدر واحد للحدود والأسعار والميزات."""
from __future__ import annotations

import copy
from typing import Any

# باقة عامة واحدة — ترتيب العرض في الواجهات التسويقية / كتالوج المنصة
DEFAULT_PLAN_KEY = 'liftcore'
PLAN_ORDER = (DEFAULT_PLAN_KEY,)
# باقات قديمة تُعامل كالباقة الموحدة عند احتساب الحدود
LEGACY_PLAN_KEYS = frozenset({'basic', 'plus', 'pro', 'enterprise'})
# باقة تُبنى يدوياً لكل عميل من لوحة المنصة فقط — ليست للبيع العام
CUSTOM_PLAN_KEY = 'custom'

_ALL_FEATURES_TRUE: dict[str, bool] = {
    'maintenance_core': True,
    'inventory': True,
    'purchasing': True,
    'advanced_finance': True,
    'excel_import': True,
    'installation': True,
    'zatca_phase2': True,
    'priority_support': True,
}

PLAN_CATALOG: dict[str, dict[str, Any]] = {
    'liftcore': {
        'label': 'LiftCore',
        'label_ar': 'LiftCore',
        'yearly_sar': 2399.0,
        'monthly_sar': round(2399.0 / 12, 2),
        'limits': {
            'elevators': 500,
            'office_users': 8,
            'technicians': 50,
            'storage_gb': 8,
        },
        'features': dict(_ALL_FEATURES_TRUE),
    },
    'custom': {
        'label': 'Custom',
        'label_ar': 'تخصيص',
        'yearly_sar': 0.0,
        'monthly_sar': 0.0,
        'limits': {
            'elevators': 0,
            'office_users': 0,
            'technicians': 0,
            'storage_gb': 0,
        },
        'features': {
            'maintenance_core': False,
            'inventory': False,
            'purchasing': False,
            'advanced_finance': False,
            'excel_import': False,
            'installation': False,
            'zatca_phase2': False,
            'priority_support': False,
        },
    },
}

# إضافات تُدار لكل عميل من لوحة المنصة
ADDON_CATALOG: dict[str, dict[str, Any]] = {
    'elevator_unit': {
        'label': 'مصعد إضافي',
        'label_en': 'Extra elevator',
        'kind': 'limit',
        'limit_key': 'elevators',
        'qty_per_unit': 1,
        'monthly_sar': 5.0,
        'yearly_sar': 60.0,
        'allow_qty': True,
        'min_qty': 1,
        'max_qty': 5000,
    },
    'office_user': {
        'label': 'مستخدم مكتبي إضافي',
        'label_en': 'Extra office user',
        'kind': 'limit',
        'limit_key': 'office_users',
        'qty_per_unit': 1,
        'monthly_sar': 40.0,
        'yearly_sar': 480.0,
        'allow_qty': True,
        'min_qty': 1,
        'max_qty': 200,
    },
    'storage_gb_unit': {
        'label': '1 GB تخزين إضافي',
        'label_en': 'Extra 1 GB storage',
        'kind': 'limit',
        'limit_key': 'storage_gb',
        'qty_per_unit': 1,
        'monthly_sar': 45.0,
        'yearly_sar': 540.0,
        'allow_qty': True,
        'min_qty': 1,
        'max_qty': 500,
    },
    # توافق خلفي — إضافات قديمة على مؤسسات موجودة
    'elevators_10': {
        'label': '+10 مصاعد (قديم)',
        'label_en': '+10 elevators (legacy)',
        'kind': 'limit',
        'limit_key': 'elevators',
        'qty_per_unit': 10,
        'monthly_sar': 50.0,
        'yearly_sar': 600.0,
        'allow_qty': True,
        'min_qty': 1,
        'max_qty': 100,
        'legacy': True,
    },
    'storage_10gb': {
        'label': '+10 GB تخزين (قديم)',
        'label_en': '+10 GB storage (legacy)',
        'kind': 'limit',
        'limit_key': 'storage_gb',
        'qty_per_unit': 10,
        'monthly_sar': 450.0,
        'yearly_sar': 5400.0,
        'allow_qty': True,
        'min_qty': 1,
        'max_qty': 50,
        'legacy': True,
    },
    'technician': {
        'label': 'فني ميدان (قديم)',
        'label_en': 'Technician (legacy)',
        'kind': 'limit',
        'limit_key': 'technicians',
        'qty_per_unit': 1,
        'monthly_sar': 40.0,
        'yearly_sar': 480.0,
        'allow_qty': True,
        'min_qty': 1,
        'max_qty': 200,
        'legacy': True,
    },
    'installation': {
        'label': 'وحدة التركيب (قديم)',
        'label_en': 'Installation module (legacy)',
        'kind': 'feature',
        'feature_key': 'installation',
        'monthly_sar': 0.0,
        'yearly_sar': 0.0,
        'allow_qty': False,
        'min_qty': 1,
        'max_qty': 1,
        'legacy': True,
    },
    'zatca_phase2': {
        'label': 'ZATCA Phase 2 (قديم)',
        'label_en': 'ZATCA Phase 2 (legacy)',
        'kind': 'feature',
        'feature_key': 'zatca_phase2',
        'monthly_sar': 0.0,
        'yearly_sar': 0.0,
        'allow_qty': False,
        'min_qty': 1,
        'max_qty': 1,
        'legacy': True,
    },
    'priority_support': {
        'label': 'دعم أولوية (قديم)',
        'label_en': 'Priority support (legacy)',
        'kind': 'feature',
        'feature_key': 'priority_support',
        'monthly_sar': 0.0,
        'yearly_sar': 0.0,
        'allow_qty': False,
        'min_qty': 1,
        'max_qty': 1,
        'legacy': True,
    },
    'inventory_pack': {
        'label': 'مخزون ومشتريات (قديم)',
        'label_en': 'Inventory pack (legacy)',
        'kind': 'feature_pack',
        'feature_keys': ('inventory', 'purchasing', 'advanced_finance', 'excel_import'),
        'monthly_sar': 0.0,
        'yearly_sar': 0.0,
        'allow_qty': False,
        'min_qty': 1,
        'max_qty': 1,
        'legacy': True,
    },
}

# إضافات تُعرض في صفحة الأسعار العامة
ADDON_PUBLIC_ORDER = ('elevator_unit', 'office_user', 'storage_gb_unit')

LIMIT_KEYS = ('elevators', 'office_users', 'technicians', 'storage_gb')
LIMIT_LABELS_AR = {
    'elevators': 'المصاعد',
    'office_users': 'المستخدمون المكتبيون',
    'technicians': 'الفنيون',
    'storage_gb': 'التخزين (GB)',
}

FEATURE_KEYS = (
    'maintenance_core',
    'inventory',
    'purchasing',
    'advanced_finance',
    'excel_import',
    'installation',
    'zatca_phase2',
    'priority_support',
)
FEATURE_LABELS_AR = {
    'maintenance_core': 'الصيانة الأساسية',
    'inventory': 'المخزون',
    'purchasing': 'المشتريات',
    'advanced_finance': 'المالية المتقدمة',
    'excel_import': 'استيراد Excel',
    'installation': 'وحدة التركيب',
    'zatca_phase2': 'ZATCA Phase 2',
    'priority_support': 'دعم أولوية',
}


def normalize_plan(plan: str | None) -> str:
    key = (plan or DEFAULT_PLAN_KEY).strip().lower()
    if key == CUSTOM_PLAN_KEY:
        return CUSTOM_PLAN_KEY
    if key in LEGACY_PLAN_KEYS:
        return DEFAULT_PLAN_KEY
    catalog = _safe_live_plans()
    return key if key in catalog else DEFAULT_PLAN_KEY


def _safe_live_plans() -> dict[str, dict[str, Any]]:
    try:
        from platform_catalog_store import live_plan_catalog
        return live_plan_catalog()
    except Exception:
        return {k: PLAN_CATALOG[k] for k in PLAN_ORDER}


def _safe_live_addons() -> dict[str, dict[str, Any]]:
    try:
        from platform_catalog_store import live_addon_catalog
        return live_addon_catalog()
    except Exception:
        return ADDON_CATALOG


def plan_definition(plan: str | None) -> dict[str, Any]:
    key = normalize_plan(plan)
    if key == CUSTOM_PLAN_KEY:
        return copy.deepcopy(PLAN_CATALOG[CUSTOM_PLAN_KEY])
    return _safe_live_plans()[key]


def addon_definition(addon_key: str | None) -> dict[str, Any] | None:
    key = (addon_key or '').strip().lower()
    return _safe_live_addons().get(key)


def known_plan_keys() -> tuple[str, ...]:
    """باقات قابلة للتعيين على مؤسسة (يشمل التخصيص اليدوي)."""
    return PLAN_ORDER + (CUSTOM_PLAN_KEY,)


def known_addon_keys() -> tuple[str, ...]:
    return tuple(_safe_live_addons().keys()) or tuple(ADDON_CATALOG.keys())


def public_addon_keys() -> tuple[str, ...]:
    live = _safe_live_addons()
    return tuple(k for k in ADDON_PUBLIC_ORDER if k in live)
