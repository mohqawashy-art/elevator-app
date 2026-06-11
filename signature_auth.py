"""LiftCore — التحقق من التوقيع بالهوية ورمز PIN."""

from __future__ import annotations

import re
import time
from typing import Any

from flask import session

from models import Settings, Technician

SIGN_PIN_RE = re.compile(r'^\d{6}$')
SIGN_MAX_FAILS = 5
SIGN_LOCK_SECONDS = 60


def normalize_national_id(value: str | None) -> str:
    return re.sub(r'\D', '', str(value or '').strip())


def validate_sign_pin(pin: str | None) -> bool:
    return bool(pin and SIGN_PIN_RE.match(str(pin).strip()))


def _sign_lock_message() -> str | None:
    locked_until = session.get('sign_locked_until')
    if locked_until and time.time() < locked_until:
        return 'محاولات كثيرة — انتظر دقيقة ثم أعد المحاولة'
    if locked_until and time.time() >= locked_until:
        session.pop('sign_locked_until', None)
        session['sign_fails'] = 0
    return None


def _sign_fail() -> None:
    fails = int(session.get('sign_fails') or 0) + 1
    session['sign_fails'] = fails
    if fails >= SIGN_MAX_FAILS:
        session['sign_locked_until'] = time.time() + SIGN_LOCK_SECONDS


def _sign_success() -> None:
    session['sign_fails'] = 0
    session.pop('sign_locked_until', None)


def verify_signature_credentials(
    *,
    national_id: str,
    pin: str,
    role: str,
    verify_password_fn,
    settings_row: Settings | None = None,
    visit_technician_id: int | None = None,
) -> dict[str, Any]:
    """التحقق من الهوية + PIN وإرجاع بيانات التوقيع."""
    lock_msg = _sign_lock_message()
    if lock_msg:
        return {'ok': False, 'error': lock_msg}

    nid = normalize_national_id(national_id)
    pin = str(pin or '').strip()
    if not nid or not validate_sign_pin(pin):
        _sign_fail()
        return {'ok': False, 'error': 'بيانات التوقيع غير صحيحة'}

    role_key = (role or '').strip().lower()
    if role_key in ('tech', 'technician', 'فني'):
        tech = None
        for row in Technician.query.filter(Technician.national_id.isnot(None)).all():
            if normalize_national_id(row.national_id) == nid:
                tech = row
                break
        if not tech or not tech.sign_pin_hash or not tech.signature_path:
            _sign_fail()
            return {'ok': False, 'error': 'بيانات التوقيع غير صحيحة'}
        if visit_technician_id and tech.id != visit_technician_id:
            _sign_fail()
            return {'ok': False, 'error': 'هذا الفني غير مخصص لهذه الزيارة'}
        if not verify_password_fn(tech.sign_pin_hash, pin):
            _sign_fail()
            return {'ok': False, 'error': 'بيانات التوقيع غير صحيحة'}
        _sign_success()
        return {
            'ok': True,
            'name': tech.name,
            'role': 'technician',
            'person_id': tech.id,
            'signature_path': tech.signature_path,
        }

    if role_key in ('manager', 'rep', 'مدير'):
        s = settings_row
        if not s or normalize_national_id(s.rep_national_id) != nid:
            _sign_fail()
            return {'ok': False, 'error': 'بيانات التوقيع غير صحيحة'}
        if not s.rep_sign_pin_hash or not s.rep_signature_path:
            _sign_fail()
            return {'ok': False, 'error': 'بيانات التوقيع غير صحيحة'}
        if not verify_password_fn(s.rep_sign_pin_hash, pin):
            _sign_fail()
            return {'ok': False, 'error': 'بيانات التوقيع غير صحيحة'}
        _sign_success()
        return {
            'ok': True,
            'name': s.rep_name or 'ممثل الشركة',
            'role': 'manager',
            'person_id': None,
            'signature_path': s.rep_signature_path,
        }

    return {'ok': False, 'error': 'نوع التوقيع غير معروف'}
