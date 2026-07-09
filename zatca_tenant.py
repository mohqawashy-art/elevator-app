"""زاتكا لكل مؤسسة — تشفير الاعتمادات وحارس الفواتير الضريبية."""

from __future__ import annotations

import base64
import os

from flask import abort

from signature_crypto import decrypt_bytes, encrypt_bytes
from tenant_scope import tenant_query
from zatca_qr import is_tax_invoice


def zatca_encryption_secret() -> str:
    return (
        os.environ.get('LIFTCORE_ZATCA_ENCRYPTION_KEY', '').strip()
        or os.environ.get('SECRET_KEY', '').strip()
        or 'liftcore-dev-zatca-key'
    )


def encrypt_zatca_field(plain: str | None) -> str | None:
    text = (plain or '').strip()
    if not text:
        return None
    token = encrypt_bytes(text.encode('utf-8'), zatca_encryption_secret())
    return base64.b64encode(token).decode('ascii')


def decrypt_zatca_field(token: str | None) -> str | None:
    raw = (token or '').strip()
    if not raw:
        return None
    try:
        data = decrypt_bytes(base64.b64decode(raw.encode('ascii')), zatca_encryption_secret())
    except (ValueError, TypeError):
        return None
    return data.decode('utf-8')


def active_zatca_credentials():
    from models import ZatcaCredentials

    return tenant_query(ZatcaCredentials).filter_by(status='active').first()


def tax_invoice_zatca_error(invoice_type: str | None) -> str | None:
    """رسالة خطأ إن لم تتوفر اعتمادات زاتكا نشطة — أو None."""
    if not is_tax_invoice(invoice_type):
        return None
    creds = active_zatca_credentials()
    if creds and (creds.vat_number or '').strip():
        return None
    return 'أكمل إعداد الفوترة الإلكترونية أولاً من الإعدادات'


def require_tax_invoice_zatca(invoice_type: str | None):
    """يرفض إصدار فاتورة ضريبية بدون اعتمادات tenant نشطة."""
    err = tax_invoice_zatca_error(invoice_type)
    if err:
        abort(422, description=err)
    return active_zatca_credentials()


def tenant_vat_number() -> str:
    """الرقم الضريبي للمؤسسة النشطة — من اعتمادات زاتكا فقط."""
    creds = active_zatca_credentials()
    if creds and creds.vat_number:
        return (creds.vat_number or '').strip().replace(' ', '')
    return ''
