"""رابط عام موقّع لتقرير عطل — للعميل بدون تسجيل دخول."""

from __future__ import annotations

import os
from urllib.parse import urlparse

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


_LOCAL_HOSTS = frozenset({'localhost', '127.0.0.1', '0.0.0.0', '::1'})


def _absolute_public_base(raw: str) -> str:
    text = (raw or '').strip().rstrip('/')
    if not text:
        return ''
    parsed = urlparse(text if '://' in text else f'https://{text}')
    host = (parsed.hostname or '').lower()
    if not host or host in _LOCAL_HOSTS:
        return ''
    scheme = 'https' if host.endswith('liftcoreapp.com') else (parsed.scheme or 'https')
    return f'{scheme}://{host}'


def public_base_url(base_url: str = '') -> str:
    """أصل عام كامل. لا يُرجع مساراً نسبياً ولا عنواناً داخلياً."""
    candidates = [(base_url or '').strip()]
    if has_request_context():
        candidates.append(request.url_root or '')
    candidates.append(os.environ.get('LIFTCORE_PUBLIC_BASE') or '')
    candidates.append('https://app.liftcoreapp.com')
    for raw in candidates:
        root = _absolute_public_base(raw)
        if root:
            return root
    return 'https://app.liftcoreapp.com'


def request_public_base_url() -> str:
    return public_base_url('')


def fault_report_share_url(fault_id: int, organization_id: int, base_url: str = '') -> str:
    path = fault_report_share_path(fault_id, organization_id)
    return f'{public_base_url(base_url)}{path}'
