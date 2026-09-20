"""روابط عامة موقّعة للمستندات — للعملاء والموردين بدون تسجيل دخول."""

from __future__ import annotations

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

SHARE_SALT = 'liftcore-document-share'
DEFAULT_MAX_AGE = 365 * 24 * 3600

# عرض HTML
DOC_KINDS = frozenset({
    'rfq', 'rfq_en', 'po', 'po_en', 'invoice', 'contract', 'iq', 'mq',
})
# تنزيل PDF مرفوع
FILE_KINDS = frozenset({'rfq_pdf', 'po_pdf'})


def _serializer(secret_key: str | None = None) -> URLSafeTimedSerializer:
    key = secret_key or current_app.config['SECRET_KEY']
    return URLSafeTimedSerializer(key, salt=SHARE_SALT)


def _dump(payload: dict, *, secret_key: str | None = None) -> str:
    return _serializer(secret_key).dumps(payload)


def _load(token: str, *, max_age: int = DEFAULT_MAX_AGE, secret_key: str | None = None) -> dict | None:
    if not (token or '').strip():
        return None
    try:
        data = _serializer(secret_key).loads(token.strip(), max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    return data


def make_document_share_token(
    kind: str,
    doc_id: int,
    organization_id: int,
    *,
    secret_key: str | None = None,
) -> str:
    k = (kind or '').strip()
    if k not in DOC_KINDS:
        raise ValueError(f'unsupported document kind: {k}')
    return _dump({
        't': 'doc',
        'k': k,
        'id': int(doc_id),
        'oid': int(organization_id),
    }, secret_key=secret_key)


def load_document_share_token(
    token: str,
    *,
    max_age: int = DEFAULT_MAX_AGE,
    secret_key: str | None = None,
) -> dict | None:
    data = _load(token, max_age=max_age, secret_key=secret_key)
    if not data or data.get('t') != 'doc':
        return None
    kind = (data.get('k') or '').strip()
    if kind not in DOC_KINDS:
        return None
    try:
        doc_id = int(data.get('id') or 0)
        organization_id = int(data.get('oid') or 0)
    except (TypeError, ValueError):
        return None
    if doc_id <= 0 or organization_id <= 0:
        return None
    return {'kind': kind, 'doc_id': doc_id, 'organization_id': organization_id}


def document_share_path(kind: str, doc_id: int, organization_id: int) -> str:
    tok = make_document_share_token(kind, doc_id, organization_id)
    return f'/r/d/{tok}'


def document_share_url(
    kind: str,
    doc_id: int,
    organization_id: int,
    base_url: str = '',
) -> str:
    path = document_share_path(kind, doc_id, organization_id)
    root = (base_url or '').rstrip('/')
    return f'{root}{path}' if root else path


def make_document_file_token(
    kind: str,
    doc_id: int,
    organization_id: int,
    *,
    secret_key: str | None = None,
) -> str:
    k = (kind or '').strip()
    if k not in FILE_KINDS:
        raise ValueError(f'unsupported file kind: {k}')
    return _dump({
        't': 'file',
        'k': k,
        'id': int(doc_id),
        'oid': int(organization_id),
    }, secret_key=secret_key)


def load_document_file_token(
    token: str,
    *,
    max_age: int = DEFAULT_MAX_AGE,
    secret_key: str | None = None,
) -> dict | None:
    data = _load(token, max_age=max_age, secret_key=secret_key)
    if not data or data.get('t') != 'file':
        return None
    kind = (data.get('k') or '').strip()
    if kind not in FILE_KINDS:
        return None
    try:
        doc_id = int(data.get('id') or 0)
        organization_id = int(data.get('oid') or 0)
    except (TypeError, ValueError):
        return None
    if doc_id <= 0 or organization_id <= 0:
        return None
    return {'kind': kind, 'doc_id': doc_id, 'organization_id': organization_id}


def document_file_share_path(kind: str, doc_id: int, organization_id: int) -> str:
    tok = make_document_file_token(kind, doc_id, organization_id)
    return f'/r/f/{tok}'


def document_file_share_url(
    kind: str,
    doc_id: int,
    organization_id: int,
    base_url: str = '',
) -> str:
    path = document_file_share_path(kind, doc_id, organization_id)
    root = (base_url or '').rstrip('/')
    return f'{root}{path}' if root else path
