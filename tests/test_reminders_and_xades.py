"""اختبارات تذكيرات العقود + تضمين توقيع ZATCA."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from zatca_phase2 import build_simplified_ubl_xml, invoice_hash_from_xml
from zatca_xades import embed_ecdsa_signature


def _self_signed_ec():
    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'LiftCore Test')])
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
    return key_pem, cert_pem


def test_embed_ecdsa_signature_inserts_ds_block():
    key_pem, cert_pem = _self_signed_ec()
    xml = build_simplified_ubl_xml(
        invoice_uuid='11111111-1111-1111-1111-111111111111',
        invoice_code='INV-X1',
        issue_dt=datetime(2026, 7, 10, 12, 0, 0),
        seller_name='Test',
        vat_number='300000000000003',
        line_name='Svc',
        amount=100,
        tax_amount=15,
        total=115,
    )
    inv_hash = invoice_hash_from_xml(xml)
    signed = embed_ecdsa_signature(
        xml,
        invoice_hash_b64=inv_hash,
        private_key_pem=key_pem,
        certificate_pem=cert_pem,
    )
    assert '<ds:Signature' in signed
    assert '<ds:SignatureValue>' in signed
    assert 'xmlns:ext=' in signed
    # لا يُعاد الإدراج
    again = embed_ecdsa_signature(
        signed,
        invoice_hash_b64=inv_hash,
        private_key_pem=key_pem,
        certificate_pem=cert_pem,
    )
    assert again.count('Id="LiftCoreSignature"') == 1


def test_due_contract_reminders(client):
    from app import app, db
    from models import Contract, Customer
    from operations import contract_reminder_rows, due_contract_reminders
    from tenant_scope import assign_organization

    today = date.today()
    with app.app_context():
        cust = Customer(code='C-REM1', name='عميل تذكير', phone='0500000001')
        assign_organization(cust)
        db.session.add(cust)
        db.session.flush()
        c = Contract(
            code='CN-REM1',
            customer_id=cust.id,
            start_date=today - timedelta(days=300),
            end_date=today + timedelta(days=30),
            reminder_date=today,
            status='نشط',
            value=1000,
            total=1150,
        )
        assign_organization(c)
        db.session.add(c)
        db.session.commit()

        due = due_contract_reminders(on_date=today, days_ahead=0)
        assert any(x.code == 'CN-REM1' for x in due)
        rows = contract_reminder_rows(on_date=today, days_ahead=0, company_name='جما')
        match = [r for r in rows if r['code'] == 'CN-REM1']
        assert match
        assert match[0]['whatsapp_url'].startswith('https://wa.me/')
        assert 'جما' in match[0]['message']
