"""تخزين كتالوج الباقات الحي في DB ودمجه مع القيم الافتراضية في الكود."""
from __future__ import annotations

import copy
import json
from datetime import datetime
from typing import Any

from plan_catalog import (
    ADDON_CATALOG,
    FEATURE_KEYS,
    FEATURE_LABELS_AR,
    LIMIT_KEYS,
    PLAN_CATALOG,
    PLAN_ORDER,
)


def _parse_json(raw: str | None) -> dict[str, Any]:
    if not raw or not str(raw).strip():
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _deep_merge_plan(base: dict[str, Any], overlay: dict[str, Any] | None) -> dict[str, Any]:
    out = copy.deepcopy(base)
    if not overlay or not isinstance(overlay, dict):
        return out
    for key in ('label', 'label_ar'):
        if key in overlay and overlay[key] is not None and str(overlay[key]).strip():
            out[key] = str(overlay[key]).strip()
    for key in ('monthly_sar', 'yearly_sar'):
        if key in overlay and overlay[key] is not None and str(overlay[key]).strip() != '':
            try:
                out[key] = float(overlay[key])
            except (TypeError, ValueError):
                pass
    if isinstance(overlay.get('limits'), dict):
        limits = dict(out.get('limits') or {})
        for lk in LIMIT_KEYS:
            if lk in overlay['limits'] and overlay['limits'][lk] is not None:
                try:
                    limits[lk] = int(overlay['limits'][lk])
                except (TypeError, ValueError):
                    pass
        out['limits'] = limits
    if isinstance(overlay.get('features'), dict):
        features = dict(out.get('features') or {})
        for fk in FEATURE_KEYS:
            if fk in overlay['features']:
                features[fk] = bool(overlay['features'][fk])
        out['features'] = features
    return out


def _deep_merge_addon(base: dict[str, Any], overlay: dict[str, Any] | None) -> dict[str, Any]:
    out = copy.deepcopy(base)
    if not overlay or not isinstance(overlay, dict):
        return out
    for key in ('label', 'label_en'):
        if key in overlay and overlay[key] is not None and str(overlay[key]).strip():
            out[key] = str(overlay[key]).strip()
    for key in ('monthly_sar', 'yearly_sar'):
        if key in overlay and overlay[key] is not None and str(overlay[key]).strip() != '':
            try:
                out[key] = float(overlay[key])
            except (TypeError, ValueError):
                pass
    return out


def _row():
    from models import PlatformCatalog, db

    row = db.session.get(PlatformCatalog, 1)
    if row is None:
        row = PlatformCatalog.query.first()
    return row


def load_plans_overlay() -> dict[str, Any]:
    row = _row()
    if not row:
        return {}
    return _parse_json(row.plans_json)


def load_addons_overlay() -> dict[str, Any]:
    row = _row()
    if not row:
        return {}
    return _parse_json(row.addons_json)


def live_plan_catalog() -> dict[str, dict[str, Any]]:
    overlay = load_plans_overlay()
    out: dict[str, dict[str, Any]] = {}
    for key in PLAN_ORDER:
        out[key] = _deep_merge_plan(PLAN_CATALOG[key], overlay.get(key))
    return out


def live_addon_catalog() -> dict[str, dict[str, Any]]:
    overlay = load_addons_overlay()
    out: dict[str, dict[str, Any]] = {}
    for key, base in ADDON_CATALOG.items():
        out[key] = _deep_merge_addon(base, overlay.get(key))
    return out


def catalog_meta() -> dict[str, Any]:
    row = _row()
    return {
        'updated_at': row.updated_at.isoformat(sep=' ', timespec='minutes') if row and row.updated_at else None,
        'updated_by_user_id': row.updated_by_user_id if row else None,
        'has_overrides': bool(row and (row.plans_json or row.addons_json)),
    }


def save_catalog(
    *,
    plans: dict[str, Any],
    addons: dict[str, Any],
    user_id: int | None = None,
) -> dict[str, Any]:
    from models import PlatformCatalog, db

    row = db.session.get(PlatformCatalog, 1)
    if row is None:
        row = PlatformCatalog(id=1)
        db.session.add(row)
    row.plans_json = json.dumps(plans, ensure_ascii=False, separators=(',', ':'))
    row.addons_json = json.dumps(addons, ensure_ascii=False, separators=(',', ':'))
    row.updated_at = datetime.utcnow()
    row.updated_by_user_id = user_id
    db.session.commit()
    return {'ok': True, 'meta': catalog_meta()}


def reset_catalog_to_defaults(*, user_id: int | None = None) -> dict[str, Any]:
    from models import PlatformCatalog, db

    row = db.session.get(PlatformCatalog, 1)
    if row is None:
        row = PlatformCatalog(id=1)
        db.session.add(row)
    row.plans_json = None
    row.addons_json = None
    row.updated_at = datetime.utcnow()
    row.updated_by_user_id = user_id
    db.session.commit()
    return {'ok': True, 'meta': catalog_meta()}


def parse_plans_form(form) -> dict[str, Any]:
    """حوّل حقول النموذج إلى تجاوزات باقات."""
    plans: dict[str, Any] = {}
    for key in PLAN_ORDER:
        prefix = f'plan_{key}_'
        entry: dict[str, Any] = {
            'label': (form.get(prefix + 'label') or '').strip(),
            'label_ar': (form.get(prefix + 'label_ar') or '').strip(),
            'monthly_sar': (form.get(prefix + 'monthly_sar') or '').strip(),
            'yearly_sar': (form.get(prefix + 'yearly_sar') or '').strip(),
            'limits': {},
            'features': {},
        }
        for lk in LIMIT_KEYS:
            entry['limits'][lk] = (form.get(f'{prefix}limit_{lk}') or '').strip()
        for fk in FEATURE_KEYS:
            entry['features'][fk] = form.get(f'{prefix}feature_{fk}') in ('1', 'on', 'true', 'yes')
        plans[key] = entry
    return plans


def parse_addons_form(form) -> dict[str, Any]:
    addons: dict[str, Any] = {}
    for key in ADDON_CATALOG:
        prefix = f'addon_{key}_'
        addons[key] = {
            'label': (form.get(prefix + 'label') or '').strip(),
            'monthly_sar': (form.get(prefix + 'monthly_sar') or '').strip(),
            'yearly_sar': (form.get(prefix + 'yearly_sar') or '').strip(),
        }
    return addons


def plans_editor_context() -> dict[str, Any]:
    return {
        'plans': live_plan_catalog(),
        'plan_order': PLAN_ORDER,
        'addons': live_addon_catalog(),
        'limit_keys': LIMIT_KEYS,
        'feature_keys': FEATURE_KEYS,
        'feature_labels': FEATURE_LABELS_AR,
        'meta': catalog_meta(),
        'defaults': {
            'plans': copy.deepcopy(PLAN_CATALOG),
            'addons': copy.deepcopy(ADDON_CATALOG),
        },
    }
