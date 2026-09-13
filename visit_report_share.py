"""رابط عام موقّع لمحضر صيانة — للعميل بدون تسجيل دخول."""

from __future__ import annotations

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

SHARE_SALT = 'liftcore-visit-report-share'
# 180 يوم — يكفي لمتابعة العميل وإعادة فتح التقرير
DEFAULT_MAX_AGE = 180 * 24 * 3600


def _serializer(secret_key: str | None = None) -> URLSafeTimedSerializer:
    key = secret_key or current_app.config['SECRET_KEY']
    return URLSafeTimedSerializer(key, salt=SHARE_SALT)


def make_visit_report_share_token(
    visit_id: int,
    organization_id: int,
    *,
    secret_key: str | None = None,
) -> str:
    return _serializer(secret_key).dumps({
        'vid': int(visit_id),
        'oid': int(organization_id),
    })


def load_visit_report_share_token(
    token: str,
    *,
    max_age: int = DEFAULT_MAX_AGE,
    secret_key: str | None = None,
) -> dict | None:
    if not (token or '').strip():
        return None
    ser = _serializer(secret_key)
    try:
        data = ser.loads(token.strip(), max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    try:
        vid = int(data.get('vid') or 0)
        oid = int(data.get('oid') or 0)
    except (TypeError, ValueError):
        return None
    if vid <= 0 or oid <= 0:
        return None
    return {'visit_id': vid, 'organization_id': oid}


def visit_report_share_path(visit_id: int, organization_id: int) -> str:
    token = make_visit_report_share_token(visit_id, organization_id)
    return f'/r/visit/{token}'


def visit_report_share_url(visit_id: int, organization_id: int, base_url: str = '') -> str:
    path = visit_report_share_path(visit_id, organization_id)
    root = (base_url or '').rstrip('/')
    return f'{root}{path}' if root else path
