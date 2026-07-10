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
    r = submit_simplified_report(
        xml_text='<Invoice/>',
        invoice_hash='abc',
        invoice_uuid='11111111-1111-1111-1111-111111111111',
    )
    assert r['ok'] is True
    assert r['mock'] is True
    assert r['status'] == 'reported'


def test_ecdsa_sign_and_phase2_tlv():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    from datetime import timedelta, timezone

    from zatca_crypto import certificate_public_key_b64, sign_invoice_hash
    from zatca_phase2 import build_simplified_ubl_xml, invoice_hash_from_xml
    from zatca_qr import zatca_phase2_tlv_base64

    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'ZATCA Test')])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode('ascii')
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode('ascii')

    xml = build_simplified_ubl_xml(
        invoice_uuid='11111111-1111-1111-1111-111111111111',
        invoice_code='INV-S1',
        issue_dt=datetime(2026, 7, 10, 12, 0, 0),
        seller_name='Test Co',
        vat_number='300000000000003',
        line_name='Service',
        amount=100,
        tax_amount=15,
        total=115,
    )
    inv_hash = invoice_hash_from_xml(xml)
    sig = sign_invoice_hash(inv_hash, key_pem)
    pub = certificate_public_key_b64(cert_pem)
    tlv = zatca_phase2_tlv_base64(
        seller_name='Test Co',
        vat_number='300000000000003',
        invoice_date=date(2026, 7, 10),
        invoice_total=115,
        vat_total=15,
        invoice_hash_b64=inv_hash,
        signature_b64=sig,
        public_key_b64=pub,
    )
    assert len(tlv) > 50
    assert sig
    assert pub


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
