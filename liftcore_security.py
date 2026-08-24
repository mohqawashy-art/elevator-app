"""
LiftCore — أمان مركزي: CSRF، rate limit، env، كلمات مرور، uploads.
"""

from __future__ import annotations

import os
import secrets
import time
from collections import defaultdict
from threading import Lock

from flask import abort, request, session

# ── Production config ──────────────────────────────────────────────

DEFAULT_SECRET_KEYS = frozenset({
    'liftcore-secret-2025',
    'dev-secret',
    'change-me',
})

BANNED_PASSWORDS = frozenset({
    'admin123',
    '123456',
    'password',
    'liftcore',
    'admin',
    '12345678',
})

MIN_PASSWORD_LEN = 8

MAX_UPLOAD_BYTES = int(os.environ.get('LIFTCORE_MAX_UPLOAD_MB', '10')) * 1024 * 1024

ALLOWED_UPLOAD_MIME = frozenset({
    'image/png', 'image/jpeg', 'image/webp', 'image/svg+xml',
    'application/pdf',
})

# ── Rate limiting ───────────────────────────────────────────────
# افتراضياً: جدول DB مشترك بين workers (Postgres/SQLite).
# LIFTCORE_RATE_LIMIT_STORE=memory يفرض الذاكرة (اختبارات/طوارئ).

_rate_lock = Lock()
_login_attempts: dict[str, list[float]] = defaultdict(list)
_field_pin_attempts: dict[str, list[float]] = defaultdict(list)
_demo_request_attempts: dict[str, list[float]] = defaultdict(list)
_db_store_disabled = False  # يُعطّل تلقائياً إن فشل الجدول/الاتصال

LOGIN_MAX_ATTEMPTS = int(os.environ.get('LIFTCORE_LOGIN_MAX_ATTEMPTS', '5'))
LOGIN_WINDOW_SEC = int(os.environ.get('LIFTCORE_LOGIN_WINDOW_SEC', '900'))
LOGIN_LOCKOUT_SEC = int(os.environ.get('LIFTCORE_LOGIN_LOCKOUT_SEC', '900'))

FIELD_PIN_MAX_ATTEMPTS = int(os.environ.get('LIFTCORE_FIELD_PIN_MAX_ATTEMPTS', '5'))
FIELD_PIN_WINDOW_SEC = int(os.environ.get('LIFTCORE_FIELD_PIN_WINDOW_SEC', '900'))
FIELD_PIN_LOCKOUT_SEC = int(os.environ.get('LIFTCORE_FIELD_PIN_LOCKOUT_SEC', '900'))

RATE_SCOPE_LOGIN = 'login'
RATE_SCOPE_FIELD_PIN = 'field_pin'
RATE_SCOPE_DEMO = 'demo_request'

DEMO_MAX_ATTEMPTS = int(os.environ.get('LIFTCORE_DEMO_MAX_ATTEMPTS', '3'))
DEMO_WINDOW_SEC = int(os.environ.get('LIFTCORE_DEMO_WINDOW_SEC', '3600'))
DEMO_LOCKOUT_SEC = int(os.environ.get('LIFTCORE_DEMO_LOCKOUT_SEC', '3600'))


def is_production_env() -> bool:
    return os.environ.get('LIFTCORE_HTTPS', '').strip().lower() in ('1', 'true', 'yes')


def validate_production_config(app) -> None:
    """يرفض التشغيل في الإنتاج إذا SECRET_KEY ضعيف."""
    if not is_production_env():
        return
    key = (app.config.get('SECRET_KEY') or '').strip()
    if not key or key in DEFAULT_SECRET_KEYS:
        raise RuntimeError(
            'LiftCore: SECRET_KEY ضعيف أو افتراضي. '
            'عيّن متغير بيئة SECRET_KEY قبل التشغيل في الإنتاج.'
        )


def is_weak_password(plain: str) -> bool:
    p = (plain or '').strip().lower()
    if len(p) < MIN_PASSWORD_LEN:
        return True
    return p in BANNED_PASSWORDS


def password_policy_error(plain: str, *, lang: str = 'ar') -> str | None:
    p = (plain or '').strip()
    if len(p) < MIN_PASSWORD_LEN:
        return (
            f'كلمة المرور يجب أن تكون {MIN_PASSWORD_LEN} أحرف على الأقل.'
            if lang != 'en'
            else f'Password must be at least {MIN_PASSWORD_LEN} characters.'
        )
    if is_weak_password(p):
        return (
            'كلمة المرور ضعيفة أو شائعة — اختر كلمة أقوى.'
            if lang != 'en'
            else 'Password is too weak or commonly used.'
        )
    return None


# ── CSRF ─────────────────────────────────────────────────────────

CSRF_SESSION_KEY = '_csrf_token'
CSRF_FORM_FIELD = 'csrf_token'
CSRF_HEADER = 'X-CSRF-Token'

CSRF_EXEMPT_ENDPOINTS = frozenset({
    'login',
    'field_login',
    'signup',
    'api_signup',
    'onboard_form',
    'auth_handoff',
    'static',
    'web_manifest',
    'api_version',
    'moyasar_webhook',
    'whatsapp_webhook',
})


def ensure_csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_hex(32)
        session[CSRF_SESSION_KEY] = token
        session.modified = True
    return token


def validate_csrf(*, method: str, endpoint: str | None, path: str) -> None:
    from liftcore_rbac import is_exempt_path

    if method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return
    if is_exempt_path(path):
        return
    if endpoint in CSRF_EXEMPT_ENDPOINTS:
        return

    expected = session.get(CSRF_SESSION_KEY)
    if not expected:
        abort(403, description='CSRF token missing — أعد تحميل الصفحة')

    supplied = (
        request.form.get(CSRF_FORM_FIELD)
        or request.headers.get(CSRF_HEADER)
        or ''
    ).strip()
    if not supplied or not secrets.compare_digest(supplied, expected):
        abort(403, description='CSRF validation failed')


# ── Rate limit ───────────────────────────────────────────────────

def _client_ip() -> str:
    from flask import has_request_context, request
    if not has_request_context():
        return 'no-request'
    forwarded = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    return forwarded or (request.remote_addr or 'unknown')


def _force_memory_store() -> bool:
    return os.environ.get('LIFTCORE_RATE_LIMIT_STORE', '').strip().lower() in (
        'memory', 'mem', 'inmemory',
    )


def _use_db_store() -> bool:
    global _db_store_disabled
    if _db_store_disabled or _force_memory_store():
        return False
    try:
        from flask import has_app_context
        if not has_app_context():
            return False
        from models import RateLimitEvent, db  # noqa: F401
        return db.session.get_bind() is not None
    except Exception:
        return False


def _prune_attempts(bucket: dict[str, list[float]], key: str, window: float) -> None:
    now = time.time()
    bucket[key] = [t for t in bucket.get(key, []) if now - t < window]


def _memory_rate_limit_check(
    bucket: dict[str, list[float]],
    key: str,
    *,
    max_attempts: int,
    window_sec: int,
    lockout_sec: int,
) -> tuple[bool, int]:
    now = time.time()
    with _rate_lock:
        _prune_attempts(bucket, key, window_sec)
        attempts = bucket.get(key, [])
        if len(attempts) >= max_attempts:
            oldest = min(attempts)
            retry = int(lockout_sec - (now - oldest)) + 1
            return False, max(retry, 1)
        return True, 0


def _memory_record_failure(bucket: dict[str, list[float]], key: str) -> None:
    with _rate_lock:
        bucket[key].append(time.time())


def _memory_clear_attempts(bucket: dict[str, list[float]], key: str) -> None:
    with _rate_lock:
        bucket.pop(key, None)


def _db_session():
    """جلسة مستقلة — لا تُcommit معاملة الطلب الحالية بالخطأ."""
    from sqlalchemy.orm import Session

    from models import db

    return Session(bind=db.engine)


def _db_prune(session, scope: str, key: str, keep_sec: float) -> None:
    from models import RateLimitEvent

    cutoff = time.time() - keep_sec
    (
        session.query(RateLimitEvent)
        .filter(
            RateLimitEvent.scope == scope,
            RateLimitEvent.bucket_key == key,
            RateLimitEvent.created_at < cutoff,
        )
        .delete(synchronize_session=False)
    )


def _db_rate_limit_check(
    scope: str,
    key: str,
    *,
    max_attempts: int,
    window_sec: int,
    lockout_sec: int,
) -> tuple[bool, int]:
    global _db_store_disabled
    from models import RateLimitEvent

    now = time.time()
    try:
        with _db_session() as session:
            _db_prune(session, scope, key, max(window_sec, lockout_sec))
            rows = (
                session.query(RateLimitEvent.created_at)
                .filter(
                    RateLimitEvent.scope == scope,
                    RateLimitEvent.bucket_key == key,
                    RateLimitEvent.created_at >= now - window_sec,
                )
                .order_by(RateLimitEvent.created_at.asc())
                .all()
            )
            session.commit()
            timestamps = [r[0] for r in rows]
    except Exception:
        _db_store_disabled = True
        return True, 0

    if len(timestamps) >= max_attempts:
        oldest = timestamps[0]
        retry = int(lockout_sec - (now - oldest)) + 1
        return False, max(retry, 1)
    return True, 0


def _db_record_failure(scope: str, key: str) -> None:
    global _db_store_disabled
    from models import RateLimitEvent

    try:
        with _db_session() as session:
            session.add(RateLimitEvent(
                scope=scope,
                bucket_key=key[:191],
                created_at=time.time(),
            ))
            session.commit()
    except Exception:
        _db_store_disabled = True


def _db_clear_attempts(scope: str, key: str) -> None:
    global _db_store_disabled
    from models import RateLimitEvent

    try:
        with _db_session() as session:
            (
                session.query(RateLimitEvent)
                .filter(
                    RateLimitEvent.scope == scope,
                    RateLimitEvent.bucket_key == key,
                )
                .delete(synchronize_session=False)
            )
            session.commit()
    except Exception:
        _db_store_disabled = True


def _rate_limit_check(
    bucket: dict[str, list[float]],
    key: str,
    *,
    scope: str,
    max_attempts: int,
    window_sec: int,
    lockout_sec: int,
) -> tuple[bool, int]:
    """يرجع (allowed, seconds_until_retry)."""
    if not is_production_env():
        return True, 0
    if _use_db_store():
        return _db_rate_limit_check(
            scope,
            key,
            max_attempts=max_attempts,
            window_sec=window_sec,
            lockout_sec=lockout_sec,
        )
    return _memory_rate_limit_check(
        bucket,
        key,
        max_attempts=max_attempts,
        window_sec=window_sec,
        lockout_sec=lockout_sec,
    )


def _record_failure(
    bucket: dict[str, list[float]],
    key: str,
    *,
    scope: str,
) -> None:
    if _use_db_store():
        _db_record_failure(scope, key)
        return
    _memory_record_failure(bucket, key)


def _clear_attempts(
    bucket: dict[str, list[float]],
    key: str,
    *,
    scope: str,
) -> None:
    if _use_db_store():
        _db_clear_attempts(scope, key)
        return
    _memory_clear_attempts(bucket, key)


def check_login_rate_limit() -> tuple[bool, int]:
    return _rate_limit_check(
        _login_attempts,
        _client_ip(),
        scope=RATE_SCOPE_LOGIN,
        max_attempts=LOGIN_MAX_ATTEMPTS,
        window_sec=LOGIN_WINDOW_SEC,
        lockout_sec=LOGIN_LOCKOUT_SEC,
    )


def record_login_failure() -> None:
    _record_failure(_login_attempts, _client_ip(), scope=RATE_SCOPE_LOGIN)


def clear_login_attempts() -> None:
    _clear_attempts(_login_attempts, _client_ip(), scope=RATE_SCOPE_LOGIN)


def check_field_pin_rate_limit(login_id: str) -> tuple[bool, int]:
    key = f'{_client_ip()}:{(login_id or "").strip().lower()}'
    return _rate_limit_check(
        _field_pin_attempts,
        key,
        scope=RATE_SCOPE_FIELD_PIN,
        max_attempts=FIELD_PIN_MAX_ATTEMPTS,
        window_sec=FIELD_PIN_WINDOW_SEC,
        lockout_sec=FIELD_PIN_LOCKOUT_SEC,
    )


def record_field_pin_failure(login_id: str) -> None:
    key = f'{_client_ip()}:{(login_id or "").strip().lower()}'
    _record_failure(_field_pin_attempts, key, scope=RATE_SCOPE_FIELD_PIN)


def clear_field_pin_attempts(login_id: str) -> None:
    key = f'{_client_ip()}:{(login_id or "").strip().lower()}'
    _clear_attempts(_field_pin_attempts, key, scope=RATE_SCOPE_FIELD_PIN)


def check_demo_request_rate_limit() -> tuple[bool, int]:
    return _rate_limit_check(
        _demo_request_attempts,
        _client_ip(),
        scope=RATE_SCOPE_DEMO,
        max_attempts=DEMO_MAX_ATTEMPTS,
        window_sec=DEMO_WINDOW_SEC,
        lockout_sec=DEMO_LOCKOUT_SEC,
    )


def record_demo_request_attempt() -> None:
    _record_failure(_demo_request_attempts, _client_ip(), scope=RATE_SCOPE_DEMO)


# ── Upload validation ──────────────────────────────────────────────

def validate_upload_file(file_storage, *, allowed_ext: set[str]) -> tuple[bool, str]:
    """يرجع (ok, error_message_ar)."""
    if not file_storage or not file_storage.filename:
        return True, ''

    filename = file_storage.filename
    if '.' not in filename:
        return False, 'امتداد الملف غير صالح'
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in allowed_ext:
        return False, f'نوع الملف .{ext} غير مسموح'

    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        return False, f'حجم الملف يتجاوز {mb} ميجابايت'

    ctype = (getattr(file_storage, 'content_type', None) or '').split(';')[0].strip().lower()
    if ctype and ctype not in ALLOWED_UPLOAD_MIME and ctype != 'application/octet-stream':
        if ext == 'svg' and ctype in ('text/xml', 'application/xml'):
            pass
        else:
            return False, 'نوع MIME للملف غير مسموح'

    return True, ''
