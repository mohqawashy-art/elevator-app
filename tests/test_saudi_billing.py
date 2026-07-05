"""اختبارات المحاسبة السعودية — فاتورة كاملة + سند قبض تلقائي."""
from datetime import date

from models import Contract, Customer, Invoice, Revenue, Settings, db

from tests.conftest import login_as


def _seed_customer_contract(client, total=11500.0):
    with client.application.app_context():
        c = Customer(code='C-SA01', name='عميل سعودي', phone='512345678', status='نشط')
        db.session.add(c)
        db.session.flush()
        contract = Contract(
            code='CN-SA01',
            customer_id=c.id,
            contract_type='صيانة',
            start_date=date.today(),
            end_date=date.today(),
            total=total,
            status='نشط',
        )
        db.session.add(contract)
        db.session.commit()
        return c.id, contract.id, total


def test_receipt_voucher_created_on_revenue(client):
    login_as(client, 'admin')
    cid, contract_id, _ = _seed_customer_contract(client)

    with client.application.app_context():
        inv = Invoice(
            code='INV-SA01',
            invoice_type='فاتورة ضريبية',
            customer_id=cid,
            contract_id=contract_id,
            invoice_date=date.today(),
            amount=10000,
            tax_amount=1500,
            total=11500,
            status='غير مدفوعة',
        )
        db.session.add(inv)
        db.session.commit()
        inv_id = inv.id

    r = client.post('/revenues/add', data={
        'customer_id': cid,
        'revenue_date': date.today().isoformat(),
        'revenue_type': 'تجديد عقد',
        'payment_method': 'تحويل',
        'amount': '4347.83',
        'total': '5000',
        'tax_pct': '15',
        'status': 'محصّل',
        'source_type': 'invoice',
        'source_id': inv_id,
    }, follow_redirects=False)
    assert r.status_code in (302, 303)

    with client.application.app_context():
        rev = Revenue.query.filter_by(customer_id=cid).first()
        assert rev is not None
        assert rev.invoice_id == inv_id
        receipt = Invoice.query.filter_by(revenue_id=rev.id).first()
        assert receipt is not None
        assert receipt.invoice_type == 'سند قبض'
        assert receipt.code.startswith('RCP-')
        assert receipt.total == 5000
        assert receipt.parent_invoice_id == inv_id
        inv = db.session.get(Invoice, inv_id)
        assert inv.status == 'مدفوع جزئياً'
        assert inv.paid_amount == 5000


def test_tax_invoice_must_be_full_contract_amount(client):
    login_as(client, 'admin')
    cid, contract_id, total = _seed_customer_contract(client, total=11500.0)

    r = client.post('/invoices/add', data={
        'customer_id': cid,
        'contract_id': contract_id,
        'source_type': 'contract',
        'source_id': contract_id,
        'invoice_type': 'فاتورة ضريبية',
        'invoice_date': date.today().isoformat(),
        'description': 'عقد صيانة',
        'amount': '3000',
        'status': 'غير مدفوعة',
    }, follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        assert Invoice.query.filter_by(contract_id=contract_id, invoice_type='فاتورة ضريبية').count() == 0

    r2 = client.post('/invoices/add', data={
        'customer_id': cid,
        'contract_id': contract_id,
        'source_type': 'contract',
        'source_id': contract_id,
        'invoice_type': 'فاتورة ضريبية',
        'invoice_date': date.today().isoformat(),
        'description': 'عقد صيانة',
        'amount': '10000',
        'status': 'غير مدفوعة',
    }, follow_redirects=False)
    assert r2.status_code in (302, 303)
    with client.application.app_context():
        inv = Invoice.query.filter_by(contract_id=contract_id, invoice_type='فاتورة ضريبية').first()
        assert inv is not None
        assert abs(inv.total - total) < 0.02


def test_statement_links_invoice_and_receipt(client):
    login_as(client, 'admin')
    cid, contract_id, total = _seed_customer_contract(client)

    with client.application.app_context():
        inv = Invoice(
            code='INV-ST01',
            invoice_type='فاتورة ضريبية',
            customer_id=cid,
            contract_id=contract_id,
            invoice_date=date.today(),
            amount=10000,
            tax_amount=1500,
            total=total,
            status='غير مدفوعة',
        )
        db.session.add(inv)
        db.session.commit()
        inv_id = inv.id

    client.post('/revenues/add', data={
        'customer_id': cid,
        'revenue_date': date.today().isoformat(),
        'revenue_type': 'تجديد عقد',
        'amount': '4347.83',
        'total': '5000',
        'tax_pct': '15',
        'status': 'محصّل',
        'source_type': 'invoice',
        'source_id': inv_id,
    })

    r = client.get(f'/api/customers/{cid}/statement')
    assert r.status_code == 200
    data = r.get_json()
    assert data['total_invoiced'] == total
    assert data['total_paid'] == 5000
    assert len(data['debits']) == 1
    assert len(data['credits']) == 1
    assert data['credits'][0]['receipt_code'].startswith('RCP-')
