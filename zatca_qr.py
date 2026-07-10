"""رمز QR للفاتورة الضريبية المبسطة — المرحلة الأولى (هيئة الزكاة والضريبة)."""

from __future__ import annotations

import base64
from datetime import date, datetime, time


def _tlv(tag: int, value: str) -> bytes:
    encoded = value.encode('utf-8')
    if len(encoded) > 255:
        raise ValueError(f'حقل TLV طويل جداً (tag {tag})')
    return bytes([tag, len(encoded)]) + encoded


def zatca_phase1_tlv_base64(
    seller_name: str,
    vat_number: str,
    invoice_date: date,
    invoice_total: float,
    vat_total: float,
    *,
    timestamp: datetime | None = None,
) -> str:
    """
    TLV حسب مواصفات ZATCA للفواتير المبسطة:
    1 اسم البائع، 2 الرقم الضريبي، 3 التاريخ والوقت، 4 الإجمالي شامل الضريبة، 5 مبلغ الضريبة.
    """
    ts = timestamp or datetime.combine(invoice_date, time(12, 0, 0))
    ts_str = ts.strftime('%Y-%m-%dT%H:%M:%SZ')
    payload = (
        _tlv(1, (seller_name or '').strip())
        + _tlv(2, (vat_number or '').strip())
        + _tlv(3, ts_str)
        + _tlv(4, f'{float(invoice_total):.2f}')
        + _tlv(5, f'{float(vat_total):.2f}')
    )
    return base64.b64encode(payload).decode('ascii')


def zatca_phase2_tlv_base64(
    seller_name: str,
    vat_number: str,
    invoice_date: date,
    invoice_total: float,
    vat_total: float,
    invoice_hash_b64: str,
    signature_b64: str,
    public_key_b64: str,
    *,
    timestamp: datetime | None = None,
) -> str:
    """
    TLV المرحلة الثانية للفواتير المبسطة:
    1–5 كما في Phase 1، ثم 6 hash، 7 توقيع، 8 المفتاح العام/الشهادة.
    """
    ts = timestamp or datetime.combine(invoice_date, time(12, 0, 0))
    ts_str = ts.strftime('%Y-%m-%dT%H:%M:%SZ')
    payload = (
        _tlv(1, (seller_name or '').strip())
        + _tlv(2, (vat_number or '').strip())
        + _tlv(3, ts_str)
        + _tlv(4, f'{float(invoice_total):.2f}')
        + _tlv(5, f'{float(vat_total):.2f}')
        + _tlv(6, (invoice_hash_b64 or '').strip())
        + _tlv(7, (signature_b64 or '').strip())
        + _tlv(8, (public_key_b64 or '').strip())
    )
    return base64.b64encode(payload).decode('ascii')


def zatca_qr_image_data_url(tlv_base64: str, *, box_size: int = 5) -> str | None:
    """صورة PNG مضمّنة (data URL) لرمز QR — بدون اعتماد على CDN."""
    if not tlv_base64:
        return None
    try:
        import base64
        import io

        import qrcode
        from qrcode.constants import ERROR_CORRECT_M
    except ImportError:
        return None

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(tlv_base64)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#1a3a5c', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    return f'data:image/png;base64,{b64}'


def is_tax_invoice(invoice_type: str | None) -> bool:
    """سند القبض ليس فاتورة ضريبية."""
    t = (invoice_type or '').strip()
    if not t:
        return True
    if 'سند' in t:
        return False
    if 'إشعار' in t:
        return False
    return True
