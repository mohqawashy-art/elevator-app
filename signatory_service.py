"""LiftCore — إدارة الموقّعين وتشفير التوقيعات."""

from __future__ import annotations

import os

from models import Signatory, db
from signature_auth import normalize_national_id, validate_sign_pin
from signature_crypto import encrypted_signature_path, save_encrypted_signature


def upsert_signatory(
    *,
    name: str,
    national_id: str,
    role: str,
    pin_plain: str,
    pin_hash_fn,
    image_bytes: bytes | None,
    app_root: str,
    secret: str,
    technician_id: int | None = None,
    signatory_id: int | None = None,
) -> Signatory:
    nid = normalize_national_id(national_id)
    if not nid:
        raise ValueError('رقم الهوية مطلوب')
    if not (name or '').strip():
        raise ValueError('الاسم مطلوب')

    role_key = (role or 'technician').strip().lower()
    if role_key in ('فني',):
        role_key = 'technician'
    if role_key in ('مدير',):
        role_key = 'manager'
    if role_key not in ('technician', 'manager'):
        role_key = 'technician'

    row = Signatory.query.get(signatory_id) if signatory_id else None
    if not row and technician_id:
        row = Signatory.query.filter_by(technician_id=technician_id).first()
    for existing in Signatory.query.filter_by(is_active=True).all():
        if normalize_national_id(existing.national_id) == nid and (not row or existing.id != row.id):
            raise ValueError('رقم الهوية مسجّل لموقّع آخر')

    pin = (pin_plain or '').strip()
    if not row and not pin:
        raise ValueError('كلمة مرور التوقيع (6 أرقام) مطلوبة')
    if pin and not validate_sign_pin(pin):
        raise ValueError('كلمة مرور التوقيع يجب أن تكون 6 أرقام')

    if not row:
        row = Signatory(name=name.strip(), national_id=nid, role=role_key, technician_id=technician_id)
        row.sign_pin_hash = pin_hash_fn(pin)
        db.session.add(row)
        db.session.flush()
    else:
        row.name = name.strip()
        row.national_id = nid
        row.role = role_key
        row.technician_id = technician_id or row.technician_id
        row.is_active = True
        if pin:
            row.sign_pin_hash = pin_hash_fn(pin)

    if image_bytes:
        rel = save_encrypted_signature(app_root, secret, row.id, image_bytes)
        row.signature_path = rel
    elif not row.signature_path:
        raise ValueError('صورة التوقيع مطلوبة')

    return row


def sync_technician_signatory(tech, *, pin_hash_fn, app_root: str, secret: str, image_bytes: bytes | None = None) -> None:
    if not tech or not tech.national_id:
        return
    if not image_bytes and not tech.signature_path and not tech.sign_pin_hash:
        return
    pin = ''
    if not Signatory.query.filter_by(technician_id=tech.id).first() and not tech.sign_pin_hash:
        return
    upsert_signatory(
        name=tech.name,
        national_id=tech.national_id,
        role='technician',
        pin_plain=pin,
        pin_hash_fn=pin_hash_fn,
        image_bytes=image_bytes,
        app_root=app_root,
        secret=secret,
        technician_id=tech.id,
    )


def delete_signatory_files(app_root: str, signatory: Signatory) -> None:
    if not signatory or not signatory.signature_path:
        return
    rel = signatory.signature_path.replace('\\', '/')
    if rel.endswith('.enc'):
        abs_path = os.path.join(app_root, rel.replace('/', os.sep))
        if os.path.isfile(abs_path):
            try:
                os.remove(abs_path)
            except OSError:
                pass
