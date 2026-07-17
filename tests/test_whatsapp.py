"""اختبارات API واتساب المالي — رسائل خطأ + نجاح."""
from datetime import date

from models import Customer, Invoice, db

from tests.conftest import login_as


def _seed_invoice(client, phone='512345678', invoice_type='فاتورة', status='غير مدفوعة'):
    with client.application.app_context():
        c = Customer(code='C-WA01', name='عميل واتساب', phone=phone, status='نشط')
        db.session.add(c)
        db.session.flush()
        inv = Invoice(
            code='INV-WA01',
            invoice_type=invoice_type,
            customer_id=c.id,
            invoice_date=date.today(),
            amount=100,
            tax_amount=15,
            total=115,
            status=status,
        )
        db.session.add(inv)
        db.session.commit()
        return inv.id


def test_financial_whatsapp_missing_invoice(client):
    login_as(client, 'admin')
    r = client.get('/api/financial/whatsapp/invoice/99999')
    assert r.status_code == 400
    data = r.get_json()
    assert data.get('error') == 'المستند غير موجود'
    assert not data.get('whatsapp_url')


def test_financial_whatsapp_no_phone(client):
    login_as(client, 'admin')
    inv_id = _seed_invoice(client, phone='')
    r = client.get(f'/api/financial/whatsapp/invoice/{inv_id}')
    assert r.status_code == 400
    data = r.get_json()
    assert 'واتساب' in (data.get('error') or '')
    assert not data.get('whatsapp_url')


def test_financial_whatsapp_receipt_not_eligible(client):
    login_as(client, 'admin')
    inv_id = _seed_invoice(client, phone='512345678', invoice_type='سند قبض')
    r = client.get(f'/api/financial/whatsapp/invoice/{inv_id}')
    assert r.status_code == 400
    data = r.get_json()
    assert 'غير مناسب' in (data.get('error') or '')


def test_financial_whatsapp_success(client):
    login_as(client, 'admin')
    inv_id = _seed_invoice(client, phone='512345678')
    r = client.get(f'/api/financial/whatsapp/invoice/{inv_id}')
    assert r.status_code == 200
    data = r.get_json()
    url = data.get('whatsapp_url') or ''
    assert url.startswith('https://wa.me/966')
    assert 'INV-WA01' in url or 'text=' in url


def test_financial_whatsapp_invalid_type(client):
    login_as(client, 'admin')
    r = client.get('/api/financial/whatsapp/unknown/1')
    assert r.status_code == 400
    assert 'غير مدعوم' in (r.get_json().get('error') or '')


def test_invoice_payment_whatsapp_alias(client):
    login_as(client, 'admin')
    inv_id = _seed_invoice(client, phone='512345678')
    r = client.get(f'/api/invoices/{inv_id}/payment-whatsapp')
    assert r.status_code == 200
    assert (r.get_json().get('whatsapp_url') or '').startswith('https://wa.me/')


def test_financial_whatsapp_requires_auth(client):
    r = client.get('/api/financial/whatsapp/invoice/1')
    assert r.status_code in (302, 303, 401, 403)


def test_build_fault_whatsapp_puts_urls_on_clean_lines(client):
    from urllib.parse import parse_qs, unquote, urlparse

    from models import Elevator, Fault, Technician
    from operations import build_fault_whatsapp

    with client.application.app_context():
        from tests.conftest import ensure_test_organization

        oid = ensure_test_organization()
        tech = Technician(organization_id=oid, code='T-WA', name='فني', phone='0501112233', status='متاح')
        cust = Customer(organization_id=oid, code='C-WA', name='عميل', status='نشط', address='مكة')
        db.session.add_all([tech, cust])
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-WA', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()
        fault = Fault(
            organization_id=oid,
            code='FA-TEST',
            elevator_id=elev.id,
            technician_id=tech.id,
            fault_type='عطل أبواب',
            client_report='اختبار',
            priority='عادية',
            status='قيد المعالجة',
        )
        db.session.add(fault)
        db.session.commit()
        wa = build_fault_whatsapp(fault, 'https://jama.liftcoreapp.com/')
        qs = parse_qs(urlparse(wa).query)
        text = unquote(qs.get('text', [''])[0])
        assert '🗺' not in text and '🔗' not in text and '🚨' not in text
        for line in text.splitlines():
            s = line.strip()
            if s.startswith('http') and '/field/fault/' in s:
                assert s.endswith(f'/field/fault/{fault.id}')
        assert text.rstrip().endswith(f'/field/fault/{fault.id}')
