"""تحقق قرب الفني من موقع العميل المسجّل — بوابة الميدان."""

from __future__ import annotations

import math
from typing import Any

from flask import request

from models import Customer, MaintenanceVisit, Fault, Settings
from operations import VISIT_AT_CLIENT, VISIT_FINISHED_AT_CLIENT
from tenant_scope import tenant_query

DEFAULT_RADIUS_M = 300

# «قيد المعالجة» من المكتب لا يعني وصول الفني — نتحقق حتى يُسجَّل responded_at
FAULT_GEOFENCE_SKIP = (
    'تم الاصلاح',
    'تم الإصلاح',
    'محلول',
    'مغلق',
    'مكتمل',
    'مكتملة',
    'انتظار قطع',
)


def field_geofence_config(settings: Settings | None = None) -> dict[str, Any]:
    if settings is None:
        settings = tenant_query(Settings).first()
    enabled = True
    radius = DEFAULT_RADIUS_M
    if settings:
        raw_enabled = getattr(settings, 'field_geofence_enabled', None)
        if raw_enabled is not None:
            enabled = bool(raw_enabled)
        raw_radius = getattr(settings, 'field_geofence_radius_m', None)
        if raw_radius:
            try:
                radius = int(raw_radius)
            except (TypeError, ValueError):
                radius = DEFAULT_RADIUS_M
    radius = max(50, min(radius, 5000))
    return {'enabled': enabled, 'radius_m': radius}


def parse_coords(lat: Any, lng: Any) -> tuple[float, float] | None:
    try:
        la = float(str(lat or '').strip())
        ln = float(str(lng or '').strip())
    except (TypeError, ValueError):
        return None
    if not (-90 <= la <= 90 and -180 <= ln <= 180):
        return None
    if abs(la) < 0.00001 and abs(ln) < 0.00001:
        return None
    return la, ln


def request_field_coords() -> tuple[float, float] | None:
    lat = request.args.get('lat') or request.headers.get('X-LC-Lat')
    lng = request.args.get('lng') or request.headers.get('X-LC-Lng')
    if request.is_json:
        body = request.get_json(silent=True) or {}
        lat = lat or body.get('lat')
        lng = lng or body.get('lng')
    return parse_coords(lat, lng)


def customer_site_coords(customer: Customer | None) -> tuple[float, float] | None:
    if not customer:
        return None
    return parse_coords(customer.lat, customer.lng)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def visit_geofence_required(visit: MaintenanceVisit) -> bool:
    st = (visit.status or '').strip()
    if st in (VISIT_AT_CLIENT, VISIT_FINISHED_AT_CLIENT, 'جارية', 'مكتملة', 'ملغاة', 'ملغية'):
        return False
    return True


def fault_geofence_required(fault: Fault) -> bool:
    st = (fault.status or '').strip()
    if st in FAULT_GEOFENCE_SKIP:
        return False
    if fault.responded_at:
        return False
    return True


def check_field_proximity(
    tech_lat: float | None,
    tech_lng: float | None,
    customer: Customer | None,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    cfg = field_geofence_config(settings)
    site = customer_site_coords(customer)
    if not cfg['enabled']:
        return {'ok': True, 'skipped': True, 'reason': 'disabled'}
    if not site:
        return {'ok': True, 'skipped': True, 'reason': 'no_site_coords'}
    if tech_lat is None or tech_lng is None:
        return {
            'ok': False,
            'error': 'فعّل خدمة الموقع (GPS) في الجوال ثم أعد المحاولة.',
            'code': 'coords_missing',
            'radius_m': cfg['radius_m'],
        }
    dist = haversine_m(tech_lat, tech_lng, site[0], site[1])
    if dist > cfg['radius_m']:
        return {
            'ok': False,
            'error': (
                f'أنت بعيد عن موقع العميل المسجّل ({int(round(dist))} م — المسموح {cfg["radius_m"]} م). '
                'اقترب من المبنى ثم أعد المحاولة.'
            ),
            'code': 'too_far',
            'distance_m': int(round(dist)),
            'radius_m': cfg['radius_m'],
        }
    return {
        'ok': True,
        'distance_m': int(round(dist)),
        'radius_m': cfg['radius_m'],
    }


def assert_field_proximity_for_visit(
    visit: MaintenanceVisit,
    tech_lat: float | None,
    tech_lng: float | None,
    *,
    settings: Settings | None = None,
) -> None:
    if not visit_geofence_required(visit):
        return
    cust = visit.elevator.customer if visit.elevator else None
    result = check_field_proximity(tech_lat, tech_lng, cust, settings=settings)
    if not result.get('ok'):
        raise PermissionError(result.get('error') or 'يجب الاقتراب من موقع العميل أولاً')


def assert_field_proximity_for_fault(
    fault: Fault,
    tech_lat: float | None,
    tech_lng: float | None,
    *,
    settings: Settings | None = None,
) -> None:
    if not fault_geofence_required(fault):
        return
    cust = fault.elevator.customer if fault.elevator else None
    result = check_field_proximity(tech_lat, tech_lng, cust, settings=settings)
    if not result.get('ok'):
        raise PermissionError(result.get('error') or 'يجب الاقتراب من موقع العميل أولاً')


def append_coords_query(url: str, coords: tuple[float, float] | None) -> str:
    if not coords or 'lat=' in url:
        return url
    join = '&' if '?' in url else '?'
    return f'{url}{join}lat={coords[0]}&lng={coords[1]}'
