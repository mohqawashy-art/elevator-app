"""رابط عام موقّع لتقرير عطل — للعميل بدون تسجيل دخول."""

from __future__ import annotations

from flask import current_app, has_request_context, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

SHARE_SALT = 'liftcore-fault-report-share'
DEFAULT_MAX_AGE = 180 * 24 * 3600


def _serializer(secret_key: str | None = None) -> URLSafeTimedSerializer:
    key = secret_key or current_app.config['SECRET_KEY']
    return URLSafeTimedSerializer(key, salt=SHARE_SALT)


def make_fault_report_share_token(
    fault_id: int,
    organization_id: int,
    *,
    secret_key: str | None = None,
) -> str:
    return _serializer(secret_key).dumps({
        'fid': int(fault_id),
        'oid': int(organization_id),
    })


def load_fault_report_share_token(
    token: str,
    *,
    max_age: int = DEFAULT_MAX_AGE,
    secret_key: str | None = None,
) -> dict | None:
    if not (token or '').strip():
        return None
    try:
        data = _serializer(secret_key).loads(token.strip(), max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    try:
        fid = int(data.get('fid') or 0)
        oid = int(data.get('oid') or 0)
    except (TypeError, ValueError):
        return None
    if fid <= 0 or oid <= 0:
        return None
    return {'fault_id': fid, 'organization_id': oid}


def fault_report_share_path(fault_id: int, organization_id: int) -> str:
    token = make_fault_report_share_token(fault_id, organization_id)
    return f'/r/fault/{token}'


def request_public_base_url() -> str:
    if not has_request_context():
        return ''
    return (request.url_root or '').rstrip('/')


def fault_report_share_url(fault_id: int, organization_id: int, base_url: str = '') -> str:
    path = fault_report_share_path(fault_id, organization_id)
    root = (base_url or '').rstrip('/') or request_public_base_url()
    return f'{root}{path}' if root else path
