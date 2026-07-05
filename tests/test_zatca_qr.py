"""H1 — ZATCA Phase 1 QR: أنواع الفواتير + طباعة + TLV."""
from __future__ import annotations

import base64
from datetime import date, datetime

import pytest

from models import Customer, Invoice, Settings, db
from zatca_qr import is_tax_invoice, zatca_phase1_tlv_base64, zatca_qr_image_data_url

from tests.conftest import login_as

VAT_15 = '300000000000003'


def _decode_tlv_fields(b64: str) -> dict[int, str]:
    raw = base64.b64decode(b64)
    pos = 0
    fields: dict[int, str] = {}
    while pos + 2 <= len(raw):
        tag = raw[pos]
        ln = raw[pos + 1]
        val = raw[pos + 2 : pos + 2 + ln].decode('utf-8')
        fields[tag] = val
        pos += 2 + ln
    return fields


def _seed_settings(**kwargs) -> Settings:
    s = Settings.query.first()
    if not s:
        s = Settings(company_name='شركة LiftCore', tax_pct=15)
        db.session.add(s)
    s.company_name = kwargs.get('company_name', 'شركة LiftCore')
    s.vat_number = kwargs.get('vat_number', VAT_15)
    s.cr_number = kwargs.get('cr_number', '1010000000')
    s.city = kwargs.get('city', 'مكة المكرمة')
    s.address = kwargs.get('address', 'حي العزيزية')
    s.tax_pct = kwargs.get('tax_pct', 15)
    db.session.commit()
    return s


def _make_invoice(**kwargs) -> Invoice:
    cust = Customer.query.first()
    if not cust:
        cust = Customer(code='C-Z01', name='عميل ZATCA', phone='512345678', city='مكة', address='شارع 1', status='نشط')
        db.session.add(cust)
        db.session.flush()
    inv = Invoice(
        code=kwargs.get('code', 'INV-Z01'),
        invoice_type=kwargs.get('invoice_type', 'فاتورة ضريبية'),
        customer_id=cust.id,
        invoice_date=kwargs.get('invoice_date', date(2026, 6, 1)),
        description=kwargs.get('description', 'صيانة مصعد'),
        amount=kwargs.get('amount', 1000.0),
        tax_amount=kwargs.get('tax_amount', 150.0),
        total=kwargs.get('total', 1150.0),
        status=kwargs.get('status', 'غير مدفوعة'),
    )
    db.session.add(inv)
    db.session.commit()
    return inv


@pytest.mark.parametrize(
    'invoice_type,expect_tax',
    [
        ('فاتورة ضريبية', True),
        ('فاتورة ضريبية مبسطة', True),
        ('سند قبض', False),
        ('إشعار دائن', False),
        ('', True),
    ],
)
def test_is_tax_invoice_types(invoice_type, expect_tax):
    assert is_tax_invoice(invoice_type) is expect_tax


def test_tlv_contains_zatca_fields():
    b64 = zatca_phase1_tlv_base64(
        seller_name='شركة LiftCore',
        vat_number=VAT_15,
        invoice_date=date(2026, 6, 15),
        invoice_total=1150.0,
        vat_total=150.0,
        timestamp=datetime(2026, 6, 15, 14, 30, 0),
    )
    fields = _decode_tlv_fields(b64)
    assert fields[1] == 'شركة LiftCore'
    assert fields[2] == VAT_15
    assert fields[3] == '2026-06-15T14:30:00Z'
    assert fields[4] == '1150.00'
    assert fields[5] == '150.00'


def test_qr_image_data_url_generated():
    tlv = zatca_phase1_tlv_base64(
        seller_name='Test',
        vat_number=VAT_15,
        invoice_date=date.today(),
        invoice_total=100.0,
        vat_total=15.0,
    )
    url = zatca_qr_image_data_url(tlv)
    assert url
    assert url.startswith('data:image/png;base64,')


@pytest.mark.parametrize(
    'invoice_type',
    ['فاتورة ضريبية', 'فاتورة ضريبية مبسطة'],
)
def test_tax_invoices_print_with_qr(client, invoice_type):
    with client.application.app_context():
        _seed_settings()
        inv = _make_invoice(invoice_type=invoice_type, code=f'INV-{invoice_type[:4]}')
        inv_id = inv.id

    login_as(client, 'admin')
    r = client.get(f'/invoices/{inv_id}/print')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'data:image/png;base64,' in html
    assert 'امسح الرمز' in html
    if 'مبسطة' in invoice_type:
        assert 'فاتورة ضريبية مبسطة' in html
    else:
        assert 'فاتورة ضريبية' in html


def test_receipt_voucher_print_without_qr(client):
    with client.application.app_context():
        _seed_settings()
        inv = _make_invoice(invoice_type='سند قبض', code='RCP-Z01', amount=500, tax_amount=0, total=500)
        inv_id = inv.id

    login_as(client, 'admin')
    r = client.get(f'/invoices/{inv_id}/print')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'سند قبض' in html
    assert 'data:image/png;base64,' not in html


def test_tax_invoice_without_vat_shows_compliance_warning(client):
    with client.application.app_context():
        _seed_settings(vat_number='')
        inv = _make_invoice(code='INV-NOVAT')
        inv_id = inv.id

    login_as(client, 'admin')
    r = client.get(f'/invoices/{inv_id}/print')
    html = r.get_data(as_text=True)
    assert 'data:image/png;base64,' not in html
    assert 'الرقم الضريبي' in html


def test_b2b_missing_customer_address_warns(client):
    with client.application.app_context():
        _seed_settings()
        cust = Customer(code='C-NOADDR', name='بدون عنوان', phone='512111222', status='نشط')
        db.session.add(cust)
        db.session.flush()
        inv = Invoice(
            code='INV-B2B',
            invoice_type='فاتورة ضريبية',
            customer_id=cust.id,
            invoice_date=date.today(),
            description='عقد صيانة',
            amount=1000,
            tax_amount=150,
            total=1150,
        )
        db.session.add(inv)
        db.session.commit()
        inv_id = inv.id

    login_as(client, 'admin')
    html = client.get(f'/invoices/{inv_id}/print').get_data(as_text=True)
    assert 'عنوان المشتري' in html