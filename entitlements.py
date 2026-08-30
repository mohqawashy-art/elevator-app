"""احتساب وتفعيل حدود الباقة والإضافات لكل مؤسسة."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from models import Elevator, Organization, OrganizationAddon, Technician, User, db
from plan_catalog import (
    ADDON_CATALOG,
    CUSTOM_PLAN_KEY,
    FEATURE_KEYS,
    FEATURE_LABELS_AR,
    LIMIT_KEYS,
    LIMIT_LABELS_AR,
    addon_definition,
    normalize_plan,
    plan_definition,
)
from tenant_scope import current_organization_id as current_org_id


def _active_addons(org_id: int) -> list[OrganizationAddon]:
    now = datetime.utcnow()
    rows = (
        OrganizationAddon.query.filter_by(organization_id=org_id, status='active')
        .order_by(OrganizationAddon.id.asc())
        .all()
    )
    active = []
    for row in rows:
        if row.starts_at and row.starts_at > now:
            continue
        if row.ends_at and row.ends_at < now:
            continue
        active.append(row)
    return active


def parse_features_override(org: Organization | None) -> dict[str, bool] | None:
    raw = getattr(org, 'features_override_json', None) if org else None
    if not raw or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    out: dict[str, bool] = {}
    for fk in FEATURE_KEYS:
        if fk in data:
            out[fk] = bool(data[fk])
    return out or None


def resolve_entitlements(org: Organization | None = None, org_id: int | None = None) -> dict[str, Any]:
    """حدود وميزات فعّالة = الباقة + الإضافات النشطة + تجاوزات يدوية."""
    if org is None:
        if org_id is None:
            org_id = current_org_id()
        org = db.session.get(Organization, org_id) if org_id else None
    if org is None:
        plan_key = 'basic'
        plan = plan_definition(plan_key)
        return {
            'plan': plan_key,
            'plan_label': plan.get('label_ar') or plan['label'],
            'limits': dict(plan['limits']),
            'features': dict(plan['features']),
            'addons': [],
            'is_custom': False,
            'usage': {'elevators': 0, 'office_users': 0, 'technicians': 0, 'storage_gb': 0},
        }

    plan_key = normalize_plan(org.plan)
    plan = plan_definition(plan_key)
    is_custom = plan_key == CUSTOM_PLAN_KEY
    limits = dict(plan['limits'])
    features = dict(plan['features'])
    if is_custom:
        features = {fk: False for fk in FEATURE_KEYS}
        override_features = parse_features_override(org)
        if override_features:
            features.update(override_features)

    addon_rows = [] if is_custom else _active_addons(org.id)
    addon_summary = []

    for row in addon_rows:
        spec = addon_definition(row.addon_key)
        if not spec:
            continue
        qty = max(1, int(row.quantity or 1))
        addon_summary.append({
            'id': row.id,
            'key': row.addon_key,
            'label': spec['label'],
            'quantity': qty,
            'unit_price_monthly': row.unit_price_monthly,
            'note': row.note,
        })
        if spec['kind'] == 'limit':
            limits[spec['limit_key']] = int(limits.get(spec['limit_key'], 0)) + (
                qty * int(spec.get('qty_per_unit') or 1)
            )
        elif spec['kind'] == 'feature':
            features[spec['feature_key']] = True
        elif spec['kind'] == 'feature_pack':
            for fk in spec.get('feature_keys') or ():
                features[fk] = True

    # تجاوزات يدوية من المنصة (لباقة التخصيص إلزامية عملياً)
    for key in LIMIT_KEYS:
        override = getattr(org, f'{key}_limit_override', None)
        if override is not None and int(override) >= 0:
            limits[key] = int(override)

    return {
        'plan': plan_key,
        'plan_label': plan.get('label_ar') or plan['label'],
        'limits': limits,
        'features': features,
        'addons': addon_summary,
        'is_custom': is_custom,
        'usage': usage_counts(org.id),
    }


def usage_counts(org_id: int) -> dict[str, int]:
    elevators = Elevator.query.filter_by(organization_id=org_id).count()
    office_users = User.query.filter_by(organization_id=org_id, is_active=True).count()
    technicians = Technician.query.filter_by(organization_id=org_id).count()
    return {
        'elevators': elevators,
        'office_users': office_users,
        'technicians': technicians,
        'storage_gb': 0,  # يُربط لاحقاً بحجم المرفقات
    }


def has_feature(feature_key: str, org: Organization | None = None) -> bool:
    ent = resolve_entitlements(org=org)
    return bool(ent['features'].get(feature_key))


def assert_capacity(resource: str, *, requested: int = 1, org_id: int | None = None) -> dict[str, Any]:
    """تحقق من السعة قبل الإنشاء. resource: elevators|office_users|technicians."""
    if resource not in ('elevators', 'office_users', 'technicians'):
        return {'ok': True}
    if org_id is None:
        org_id = current_org_id()
    if not org_id:
        return {'ok': True}
    org = db.session.get(Organization, org_id)
    ent = resolve_entitlements(org=org)
    limit = int(ent['limits'].get(resource) or 0)
    used = int(ent['usage'].get(resource) or 0)
    if used + requested > limit:
        label = LIMIT_LABELS_AR.get(resource, resource)
        return {
            'ok': False,
            'error': (
                f'وصلت للحد الأقصى من {label} في باقتك '
                f'({used}/{limit}). اطلب ترقية أو إضافة من إدارة LiftCore.'
            ),
            'used': used,
            'limit': limit,
            'resource': resource,
        }
    return {'ok': True, 'used': used, 'limit': limit, 'resource': resource}


def list_org_addons(org_id: int) -> list[OrganizationAddon]:
    return (
        OrganizationAddon.query.filter_by(organization_id=org_id)
        .order_by(OrganizationAddon.id.desc())
        .all()
    )


def upsert_org_addon(
    org: Organization,
    *,
    addon_key: str,
    quantity: int = 1,
    note: str = '',
    unit_price_monthly: float | None = None,
    status: str = 'active',
    created_by_user_id: int | None = None,
    ends_at: datetime | None = None,
) -> dict[str, Any]:
    spec = addon_definition(addon_key)
    if not spec:
        return {'ok': False, 'errors': ['إضافة غير معروفة.']}

    qty = int(quantity or 1)
    if not spec.get('allow_qty'):
        qty = 1
    qty = max(int(spec.get('min_qty') or 1), min(qty, int(spec.get('max_qty') or 1)))

    status = (status or 'active').strip().lower()
    if status not in ('active', 'cancelled'):
        status = 'active'

    price = unit_price_monthly
    if price is None:
        price = float(spec.get('monthly_sar') or 0)

    # للإضافات من نوع feature: صف واحد فقط
    existing = None
    if not spec.get('allow_qty'):
        existing = (
            OrganizationAddon.query.filter_by(
                organization_id=org.id,
                addon_key=spec and addon_key,
                status='active',
            ).first()
        )

    if existing:
        existing.quantity = qty
        existing.unit_price_monthly = float(price)
        existing.note = (note or '').strip() or None
        existing.status = status
        existing.ends_at = ends_at
        existing.updated_at = datetime.utcnow()
        row = existing
    else:
        row = OrganizationAddon(
            organization_id=org.id,
            addon_key=addon_key.strip().lower(),
            quantity=qty,
            unit_price_monthly=float(price),
            status=status,
            note=(note or '').strip() or None,
            starts_at=datetime.utcnow(),
            ends_at=ends_at,
            created_by_user_id=created_by_user_id,
        )
        db.session.add(row)

    db.session.commit()
    return {'ok': True, 'addon': row, 'entitlements': resolve_entitlements(org=org)}


def cancel_org_addon(org: Organization, addon_id: int) -> dict[str, Any]:
    row = OrganizationAddon.query.filter_by(id=addon_id, organization_id=org.id).first()
    if not row:
        return {'ok': False, 'errors': ['الإضافة غير موجودة.']}
    row.status = 'cancelled'
    row.ends_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    db.session.commit()
    return {'ok': True, 'addon': row}


def set_limit_overrides(
    org: Organization,
    *,
    elevators: int | None = None,
    office_users: int | None = None,
    technicians: int | None = None,
    storage_gb: int | None = None,
    clear: bool = False,
) -> dict[str, Any]:
    if clear:
        org.elevators_limit_override = None
        org.office_users_limit_override = None
        org.technicians_limit_override = None
        org.storage_gb_limit_override = None
    else:
        mapping = {
            'elevators_limit_override': elevators,
            'office_users_limit_override': office_users,
            'technicians_limit_override': technicians,
            'storage_gb_limit_override': storage_gb,
        }
        for attr, val in mapping.items():
            if val is None:
                continue
            try:
                n = int(val)
            except (TypeError, ValueError):
                return {'ok': False, 'errors': [f'قيمة غير صالحة: {attr}']}
            if n < 0:
                return {'ok': False, 'errors': ['الحد لا يمكن أن يكون سالباً.']}
            setattr(org, attr, n)
    db.session.commit()
    return {'ok': True, 'entitlements': resolve_entitlements(org=org)}


def set_custom_package(
    org: Organization,
    *,
    features: dict[str, bool],
    elevators: int,
    office_users: int,
    technicians: int,
    storage_gb: int,
    amount: float,
    cycle: str = 'monthly',
    billing_notes: str | None = None,
) -> dict[str, Any]:
    """باقة تخصيص كاملة: ميزات + حدود + سعر — لمشغّل المنصة فقط."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {'ok': False, 'errors': ['السعر مطلوب.']}
    if amount < 0:
        return {'ok': False, 'errors': ['السعر غير صالح.']}

    cycle = (cycle or 'monthly').strip().lower()
    if cycle not in ('monthly', 'yearly'):
        return {'ok': False, 'errors': ['دورة فوترة غير معروفة.']}

    cleaned_features: dict[str, bool] = {}
    for fk in FEATURE_KEYS:
        cleaned_features[fk] = bool(features.get(fk))
    if not any(cleaned_features.values()):
        return {'ok': False, 'errors': ['فعّل خدمة واحدة على الأقل للعميل.']}

    for label, val in (
        ('المصاعد', elevators),
        ('المستخدمون', office_users),
        ('الفنيون', technicians),
        ('التخزين', storage_gb),
    ):
        try:
            n = int(val)
        except (TypeError, ValueError):
            return {'ok': False, 'errors': [f'حد {label} غير صالح.']}
        if n < 0:
            return {'ok': False, 'errors': [f'حد {label} لا يمكن أن يكون سالباً.']}

    org.plan = CUSTOM_PLAN_KEY
    org.features_override_json = json.dumps(cleaned_features, ensure_ascii=False, separators=(',', ':'))
    org.elevators_limit_override = int(elevators)
    org.office_users_limit_override = int(office_users)
    org.technicians_limit_override = int(technicians)
    org.storage_gb_limit_override = int(storage_gb)
    org.billing_cycle = cycle
    org.billing_amount = float(amount)
    if billing_notes is not None:
        org.billing_notes = (billing_notes or '').strip() or None
    db.session.commit()
    return {'ok': True, 'org': org, 'entitlements': resolve_entitlements(org=org)}


def addon_catalog_for_ui() -> list[dict[str, Any]]:
    from plan_catalog import _safe_live_addons

    rows = []
    for key, spec in _safe_live_addons().items():
        rows.append({'key': key, **spec})
    return rows


def feature_catalog_for_ui() -> list[dict[str, str]]:
    return [{'key': fk, 'label': FEATURE_LABELS_AR.get(fk, fk)} for fk in FEATURE_KEYS]
