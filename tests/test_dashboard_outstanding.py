"""مستحق التحصيل على لوحة التحكم."""
from datetime import date, timedelta

from customer_billing import tenant_outstanding_collectible
from models import Contract, Customer, db


def test_outstanding_collectible_counts_contract_remaining(client):
    with client.application.app_context():
        cust = Customer(code='C-OS01', name='عميل مستحق', phone='511111111', status='نشط')
        db.session.add(cust)
        db.session.flush()
        today = date.today()
        c = Contract(
            code='CN-OS01',
            customer_id=cust.id,
            contract_type='صيانة',
            start_date=today,
            end_date=today + timedelta(days=180),
            total=2500,
            paid_amount=1250,
            invoice_status='مدفوع جزئياً',
            status='نشط',
        )
        db.session.add(c)
        db.session.commit()

        data = tenant_outstanding_collectible(today=today)
        assert data['contracts_count'] >= 1
        assert data['total'] >= 1250
        match = [r for r in data['rows'] if r['code'] == 'CN-OS01']
        assert match
        assert match[0]['remaining'] == 1250


def test_dashboard_includes_outstanding_collectible(client):
    from tests.conftest import login_as
    login_as(client, 'admin')
    r = client.get('/dashboard')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'مستحق التحصيل' in html


def test_tenant_uncollected_ops_lists_contract_remaining(client):
    from customer_billing import tenant_uncollected_ops
    from tests.conftest import login_as

    login_as(client, 'admin')
    with client.application.app_context():
        cust = Customer(code='C-UC01', name='عميل غير محصل', phone='522222222', status='نشط')
        db.session.add(cust)
        db.session.flush()
        today = date.today()
        c = Contract(
            code='CN-UC01',
            customer_id=cust.id,
            contract_type='صيانة',
            start_date=today,
            end_date=today + timedelta(days=180),
            total=3000,
            paid_amount=0,
            invoice_status='غير مدفوع',
            status='نشط',
        )
        db.session.add(c)
        db.session.commit()
        rows = tenant_uncollected_ops()
        match = [r for r in rows if r.get('code') == 'CN-UC01']
        assert match
        assert match[0]['customer_id'] == cust.id
        assert match[0]['remaining'] >= 3000

    r = client.get('/api/revenues/uncollected-ops')
    assert r.status_code == 200
    data = r.get_json()
    assert data['count'] >= 1
    assert any(op.get('code') == 'CN-UC01' for op in data['operations'])
