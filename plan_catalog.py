"""كتالوج باقات وإضافات LiftCore SaaS — مصدر واحد للحدود والأسعار والميزات."""
from __future__ import annotations

from typing import Any

# ترتيب العرض في الواجهات
PLAN_ORDER = ('basic', 'plus', 'pro', 'enterprise')

PLAN_CATALOG: dict[str, dict[str, Any]] = {
    'basic': {
        'label': 'Basic',
        'label_ar': 'أساسي',
        'yearly_sar': 3000.0,
        'monthly_sar': 250.0,
        'limits': {
            'elevators': 50,
            'office_users': 3,
            'technicians': 2,
            'storage_gb': 2,
        },
        'features': {
            'maintenance_core': True,
            'inventory': False,
            'purchasing': False,
            'advanced_finance': False,
            'excel_import': False,
            'installation': False,
            'zatca_phase2': False,
            'priority_support': False,
        },
    },
    'plus': {
        'label': 'Plus',
        'label_ar': 'بلس',
        'yearly_sar': 4590.0,
        'monthly_sar': 382.5,
        'limits': {
            'elevators': 50,
            'office_users': 3,
            'technicians': 2,
            'storage_gb': 2,
        },
        'features': {
            'maintenance_core': True,
            'inventory': True,
            'purchasing': True,
            'advanced_finance': True,
            'excel_import': True,
            'installation': False,
            'zatca_phase2': False,
            'priority_support': False,
        },
    },
    'pro': {
        'label': 'Pro',
        'label_ar': 'احترافي',
        'yearly_sar': 5400.0,
        'monthly_sar': 450.0,
        'limits': {
            'elevators': 150,
            'office_users': 8,
            'technicians': 10,
            'storage_gb': 8,
        },
        'features': {
            'maintenance_core': True,
            'inventory': True,
            'purchasing': True,
            'advanced_finance': True,
            'excel_import': True,
            'installation': False,
            'zatca_phase2': False,
            'priority_support': False,
        },
    },
    'enterprise': {
        'label': 'Enterprise',
        'label_ar': 'مؤسسات',
        'yearly_sar': 12000.0,
        'monthly_sar': 1000.0,
        'limits': {
            'elevators': 400,
            'office_users': 20,
            'technicians': 30,
            'storage_gb': 25,
        },
        'features': {
            'maintenance_core': True,
            'inventory': True,
            'purchasing': True,
            'advanced_finance': True,
            'excel_import': True,
            'installation': True,
            'zatca_phase2': False,
            'priority_support': True,
        },
    },
}

# إضافات تُدار لكل عميل من لوحة المنصة
ADDON_CATALOG: dict[str, dict[str, Any]] = {
    'office_user': {
        'label': 'مستخدم مكتبي',
        'label_en': 'Office user',
        'kind': 'limit',
        'limit_key': 'office_users',
        'qty_per_unit': 1,
        'monthly_sar': 15.0,
        'yearly_sar': 180.0,
        'allow_qty': True,
        'min_qty': 1,
        'max_qty': 200,
    },
    'technician': {
        'label': 'فني ميدان',
        'label_en': 'Technician',
        'kind': 'limit',
        'limit_key': 'technicians',
        'qty_per_unit': 1,
        'monthly_sar': 20.0,
        'yearly_sar': 240.0,
        'allow_qty': True,
        'min_qty': 1,
        'max_qty': 200,
    },
    'elevators_10': {
        'label': '+10 مصاعد',
        'label_en': '+10 elevators',
        'kind': 'limit',
        'limit_key': 'elevators',
        'qty_per_unit': 10,
        'monthly_sar': 40.0,
        'yearly_sar': 480.0,
        'allow_qty': True,
        'min_qty': 1,
        'max_qty': 100,
    },
    'storage_10gb': {
        'label': '+10 GB تخزين',
        'label_en': '+10 GB storage',
        'kind': 'limit',
        'limit_key': 'storage_gb',
        'qty_per_unit': 10,
        'monthly_sar': 25.0,
        'yearly_sar': 300.0,
        'allow_qty': True,
        'min_qty': 1,
        'max_qty': 50,
    },
    'installation': {
        'label': 'وحدة التركيب',
        'label_en': 'Installation module',
        'kind': 'feature',
        'feature_key': 'installation',
        'monthly_sar': 199.0,
        'yearly_sar': 1900.0,
        'allow_qty': False,
        'min_qty': 1,
        'max_qty': 1,
    },
    'zatca_phase2': {
        'label': 'ZATCA Phase 2',
        'label_en': 'ZATCA Phase 2',
        'kind': 'feature',
        'feature_key': 'zatca_phase2',
        'monthly_sar': 199.0,
        'yearly_sar': 1800.0,
        'allow_qty': False,
        'min_qty': 1,
        'max_qty': 1,
    },
    'priority_support': {
        'label': 'دعم أولوية',
        'label_en': 'Priority support',
        'kind': 'feature',
        'feature_key': 'priority_support',
        'monthly_sar': 149.0,
        'yearly_sar': 1490.0,
        'allow_qty': False,
        'min_qty': 1,
        'max_qty': 1,
    },
    'inventory_pack': {
        'label': 'مخزون ومشتريات ومالية',
        'label_en': 'Inventory & finance pack',
        'kind': 'feature_pack',
        'feature_keys': ('inventory', 'purchasing', 'advanced_finance', 'excel_import'),
        'monthly_sar': 149.0,
        'yearly_sar': 1490.0,
        'allow_qty': False,
        'min_qty': 1,
        'max_qty': 1,
    },
}

LIMIT_KEYS = ('elevators', 'office_users', 'technicians', 'storage_gb')
LIMIT_LABELS_AR = {
    'elevators': 'المصاعد',
    'office_users': 'المستخدمون المكتبيون',
    'technicians': 'الفنيون',
    'storage_gb': 'التخزين (GB)',
}


def normalize_plan(plan: str | None) -> str:
    key = (plan or 'basic').strip().lower()
    return key if key in PLAN_CATALOG else 'basic'


def plan_definition(plan: str | None) -> dict[str, Any]:
    return PLAN_CATALOG[normalize_plan(plan)]


def addon_definition(addon_key: str | None) -> dict[str, Any] | None:
    key = (addon_key or '').strip().lower()
    return ADDON_CATALOG.get(key)


def known_plan_keys() -> tuple[str, ...]:
    return PLAN_ORDER


def known_addon_keys() -> tuple[str, ...]:
    return tuple(ADDON_CATALOG.keys())
