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
