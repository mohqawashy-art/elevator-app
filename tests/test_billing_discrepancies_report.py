"""H3 — تقرير فروقات الفوترة."""
from datetime import date

from billing_consistency import billing_discrepancies_report, repair_billing_consistency
from models import Contract, Customer, Invoice, Revenue, db

from tests.conftest import login_as


def test_billing_discrepancies_report_structure(client):
    login_as(client, 'manager')
    r = client.get('/api/reports/billing-discrepancies')
    assert r.status_code == 200
    data = r.get_json()
    assert 'ok' in data
    assert 'issue_count' in data
    assert 'rows' in data
    assert 'contracts' in data
    assert 'total_abs_delta' in data


def test_report_page_manager_access(client):
    login_as(client, 'manager')
    r = client.get('/reports/billing-discrepancies')
    assert r.status_code == 200
    assert 'فروقات الفوترة' in r.get_data(as_text=True)


def test_report_api_viewer_forbidden(client):
    login_as(client, 'viewer')
    assert client.get('/api/reports/billing-discrepancies').status_code == 403


def test_report_lists_contract_mismatch(client):
    with client.application.app_context():
        cust = Customer(code='C-H3', name='عميل H3', phone='512345678', status='نشط')
        db.session.add(cust)
        db.session.flush()
        today = date.today()
        contract = Contract(
            code='CN-H3',
            customer_id=cust.id,
            contract_type='صيانة',
            start_date=today,
            end_date=today,
            total=5000,
            paid_amount=0,
            status='نشط',
        )
        db.session.add(contract)
        db.session.flush()
        rev = Revenue(
            code='REV-H3',
            customer_id=cust.id,
            contract_id=contract.id,
            revenue_date=today,
            revenue_type='عقد',
            amount=5000,
            total=5000,
            status='محصّل',
        )
        db.session.add(rev)
        db.session.commit()

    login_as(client, 'admin')
    data = client.get('/api/reports/billing-discrepancies').get_json()
    assert data['issue_count'] >= 1
    codes = [row['code'] for row in data['rows']]
    assert 'CN-H3' in codes

    repair = client.post('/api/admin/billing/consistency/repair').get_json()
    assert repair['contracts_updated'] >= 1
    after = client.get('/api/reports/billing-discrepancies').get_json()
    assert after['ok'] is True
