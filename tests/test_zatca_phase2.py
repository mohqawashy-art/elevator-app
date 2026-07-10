"""اختبارات ZATCA Phase 2 — XML + تبليغ مبسّط (mock)."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from zatca_phase2 import (
    build_simplified_ubl_xml,
    invoice_hash_from_xml,
    is_simplified_tax_invoice,
    process_simplified_invoice,
    qr_tlv_from_invoice,
    save_zatca_credentials_form,
    submit_simplified_report,
)


def test_is_simplified_tax_invoice():
    assert is_simplified_tax_invoice('فاتورة ضريبية مبسطة')
    assert not is_simplified_tax_invoice('فاتورة ضريبية')
    assert not is_simplified_tax_invoice('سند قبض')


def test_build_ubl_and_hash():
    xml = build_simplified_ubl_xml(
        invoice_uuid='11111111-1111-1111-1111-111111111111',
        invoice_code='INV-0001',
        issue_dt=datetime(2026, 7, 10, 12, 0, 0),
        seller_name='شركة اختبار',
        vat_number='300000000000003',
        line_name='صيانة',
        amount=100.0,
        tax_amount=15.0,
        total=115.0,
    )
    assert 'INV-0001' in xml
    assert '300000000000003' in xml
    assert '<cbc:UUID>11111111-1111-1111-1111-111111111111</cbc:UUID>' in xml
    h = invoice_hash_from_xml(xml)
    assert len(h) >= 40
    assert invoice_hash_from_xml(xml) == h


def test_submit_mock(monkeypatch):
    monkeypatch.setenv('LIFTCORE_ZATCA_MOCK', '1')
    r = submit_simplified_report(xml_text='<Invoice/>', invoice_hash='abc')
    assert r['ok'] is True
    assert r['mock'] is True
    assert r['status'] == 'reported'


def test_process_simplified_invoice_sets_fields(client, monkeypatch):
    monkeypatch.setenv('LIFTCORE_ZATCA_MOCK', '1')
    from app import app, db
    from models import Invoice, Settings
    from tenant_scope import assign_organization

    with app.app_context():
        s = Settings.query.first()
        assert s is not None
        inv = Invoice(
            code='INV-Z2-1',
            invoice_type='فاتورة ضريبية مبسطة',
            invoice_date=date.today(),
            description='صيانة دورية',
            amount=100,
            tax_amount=15,
            total=115,
            status='غير مدفوعة',
        )
        assign_organization(inv)
        db.session.add(inv)
        db.session.commit()

        result = process_simplified_invoice(inv, s)
        db.session.commit()

        assert result['ok'] is True
        assert inv.zatca_uuid
        assert inv.zatca_invoice_hash
        assert inv.zatca_status == 'reported'
        assert inv.zatca_reported_at is not None
        tlv = qr_tlv_from_invoice(inv)
        assert tlv


def test_save_zatca_credentials_form(client):
    from app import app
    from models import ZatcaCredentials
    from tests.conftest import login_as

    login_as(client, 'admin')
    with app.app_context():
        err = save_zatca_credentials_form({
            'zatca_vat_number': '310175397400003',
            'zatca_cr_number': '1010000000',
            'zatca_environment': 'sandbox',
            'zatca_status': 'active',
            'zatca_csid': 'test-csid-value',
            'zatca_certificate': '-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----',
            'zatca_private_key': '-----BEGIN EC PRIVATE KEY-----\nMIGH\n-----END EC PRIVATE KEY-----',
        })
        assert err is None
        creds = ZatcaCredentials.query.first()
        assert creds is not None
        assert creds.vat_number == '310175397400003'
        assert creds.csid and creds.csid != 'test-csid-value'  # مشفّر
        assert creds.certificate and 'BEGIN CERTIFICATE' not in (creds.certificate or '')
