"""دخول الفني — بوابة الجوال (منفصلة عن مستخدمي المكتب)."""

from __future__ import annotations

import re

from flask import session
from werkzeug.security import check_password_hash

from models import Technician

FIELD_SESSION_KEY = 'field_tech_id'


def normalize_phone(value: str | None) -> str:
    digits = re.sub(r'\D', '', str(value or ''))
    if digits.startswith('966') and len(digits) >= 12:
        digits = '0' + digits[3:]
    if digits.startswith('5') and len(digits) == 9:
        digits = '0' + digits
    return digits


def find_technician_by_login(login_id: str | None) -> Technician | None:
    raw = (login_id or '').strip()
    if not raw:
        return None
    by_code = Technician.query.filter(
        Technician.code.ilike(raw),
        Technician.status.in_(['نشط', 'متاح', 'مشغول']),
    ).first()
    if by_code:
        return by_code
    phone = normalize_phone(raw)
    if not phone:
        return None
    for tech in Technician.query.filter(
        Technician.status.in_(['نشط', 'متاح', 'مشغول']),
    ).all():
        if normalize_phone(tech.phone) == phone or normalize_phone(tech.phone2) == phone:
            return tech
    return None


def verify_technician_pin(tech: Technician, pin: str | None) -> bool:
    pin = str(pin or '').strip()
    if not pin or not tech.sign_pin_hash:
        return False
    return check_password_hash(tech.sign_pin_hash, pin)


def field_login_technician(tech: Technician) -> None:
    session[FIELD_SESSION_KEY] = tech.id
    session.permanent = True


def field_logout_technician() -> None:
    session.pop(FIELD_SESSION_KEY, None)


def field_session_technician_id() -> int | None:
    tid = session.get(FIELD_SESSION_KEY)
    if tid:
        return int(tid)
    return None


def technician_portal_kind(tech: Technician) -> str:
    """maintenance | faults | both"""
    team = (tech.team or 'عام').strip()
    if team == 'أعطال':
        return 'faults'
    if team == 'صيانة':
        return 'maintenance'
    return 'both'


def technician_portal_label(kind: str) -> str:
    return {
        'maintenance': 'فني صيانة',
        'faults': 'فني أعطال',
        'both': 'فني صيانة وأعطال',
    }.get(kind, 'فني ميداني')


def resolve_field_technician_id(office_preview_id: int | None = None) -> int | None:
    """معرّف الفني الحالي — جلسة الجوال أو معاينة المكتب."""
    tid = field_session_technician_id()
    if tid:
        return tid
    if office_preview_id:
        return office_preview_id
    return None
