"""LiftCore — التحقق من التوقيع بالهوية وكلمة المرور."""

from __future__ import annotations

import os
import re
import time
from typing import Any, Callable

from flask import session

from models import Settings, Signatory, Technician

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


def _find_signatory(national_id: str) -> Signatory | None:
    nid = normalize_national_id(national_id)
    if not nid:
        return None
    for row in Signatory.query.filter_by(is_active=True).all():
        if normalize_national_id(row.national_id) == nid:
            return row
    return None


def _role_matches(role_key: str, signatory: Signatory) -> bool:
    sig_role = (signatory.role or 'technician').strip().lower()
    if role_key in ('tech', 'technician', 'فني'):
        return sig_role in ('technician', 'tech', 'فني')
    if role_key in ('manager', 'rep', 'مدير'):
        return sig_role in ('manager', 'rep', 'مدير')
    return True


def _legacy_signature_path(
    *,
    national_id: str,
    role_key: str,
    settings_row: Settings | None,
    visit_technician_id: int | None,
) -> dict[str, Any] | None:
    nid = normalize_national_id(national_id)
    if role_key in ('tech', 'technician', 'فني'):
        tech = None
        for row in Technician.query.filter(Technician.national_id.isnot(None)).all():
            if normalize_national_id(row.national_id) == nid:
                tech = row
                break
        if not tech or not tech.signature_path:
            return None
        if visit_technician_id and tech.id != visit_technician_id:
            return None
        return {
            'name': tech.name,
            'role': 'technician',
            'person_id': tech.id,
            'signature_path': tech.signature_path,
            'legacy_plain': True,
        }
    if role_key in ('manager', 'rep', 'مدير') and settings_row:
        if normalize_national_id(settings_row.rep_national_id) != nid:
            return None
        if not settings_row.rep_signature_path:
            return None
        return {
            'name': settings_row.rep_name or 'ممثل الشركة',
            'role': 'manager',
            'person_id': None,
            'signature_path': settings_row.rep_signature_path,
            'legacy_plain': True,
        }
    return None


def _legacy_pin_ok(
    *,
    national_id: str,
    pin: str,
    role_key: str,
    verify_password_fn: Callable[[str, str], bool],
    settings_row: Settings | None,
) -> bool:
    nid = normalize_national_id(national_id)
    if role_key in ('tech', 'technician', 'فني'):
        for row in Technician.query.filter(Technician.national_id.isnot(None)).all():
            if normalize_national_id(row.national_id) == nid and row.sign_pin_hash:
                return verify_password_fn(row.sign_pin_hash, pin)
        return False
    if role_key in ('manager', 'rep', 'مدير') and settings_row:
        if normalize_national_id(settings_row.rep_national_id) != nid:
            return False
        if not settings_row.rep_sign_pin_hash:
            return False
        return verify_password_fn(settings_row.rep_sign_pin_hash, pin)
    return False


def verify_signature_credentials(
    *,
    national_id: str,
    pin: str,
    role: str,
    verify_password_fn,
    settings_row: Settings | None = None,
    visit_technician_id: int | None = None,
) -> dict[str, Any]:
    """التحقق من الهوية + كلمة المرور وإرجاع مسار التوقيع."""
    lock_msg = _sign_lock_message()
    if lock_msg:
        return {'ok': False, 'error': lock_msg}

    nid = normalize_national_id(national_id)
    pin = str(pin or '').strip()
    if not nid or not validate_sign_pin(pin):
        _sign_fail()
        return {'ok': False, 'error': 'رقم الهوية أو كلمة المرور غير صحيحة'}

    role_key = (role or '').strip().lower()

    signatory = _find_signatory(nid)
    if signatory and _role_matches(role_key, signatory):
        if not signatory.sign_pin_hash or not signatory.signature_path:
            _sign_fail()
            return {'ok': False, 'error': 'رقم الهوية أو كلمة المرور غير صحيحة'}
        if visit_technician_id and signatory.technician_id and signatory.technician_id != visit_technician_id:
            _sign_fail()
            return {'ok': False, 'error': 'هذا الموقّع غير مخصص لهذه الزيارة'}
        if not verify_password_fn(signatory.sign_pin_hash, pin):
            _sign_fail()
            return {'ok': False, 'error': 'رقم الهوية أو كلمة المرور غير صحيحة'}
        _sign_success()
        return {
            'ok': True,
            'name': signatory.name,
            'role': signatory.role,
            'person_id': signatory.technician_id or signatory.id,
            'signature_path': signatory.signature_path,
            'encrypted': signatory.signature_path.endswith('.enc'),
            'legacy_plain': False,
        }

    legacy = _legacy_signature_path(
        national_id=nid,
        role_key=role_key,
        settings_row=settings_row,
        visit_technician_id=visit_technician_id,
    )
    if legacy and _legacy_pin_ok(
        national_id=nid,
        pin=pin,
        role_key=role_key,
        verify_password_fn=verify_password_fn,
        settings_row=settings_row,
    ):
        _sign_success()
        legacy['ok'] = True
        legacy['encrypted'] = False
        return legacy

    _sign_fail()
    return {'ok': False, 'error': 'رقم الهوية أو كلمة المرور غير صحيحة'}
