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
