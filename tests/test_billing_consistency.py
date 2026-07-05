"""G7 — اتساق كاش العقود والفواتير."""
from datetime import date

from billing_consistency import (
    audit_billing_consistency,
    refresh_contract_cache,
    repair_billing_consistency,
    revenue_paid_for_invoice,
)
from models import Contract, Customer, Invoice, Revenue, db

from tests.conftest import login_as


def _seed_contract(total=11500.0):
    cust = Customer(code='C-BC01', name='عميل كاش', phone='512345678', status='نشط')
    db.session.add(cust)
    db.session.flush()
    today = date.today()
    contract = Contract(
        code='CN-BC01',
        customer_id=cust.id,
        contract_type='صيانة',
        start_date=today,
        end_date=today,
        total=total,
        paid_amount=0,
        status='نشط',
    )
    db.session.add(contract)
    db.session.commit()
    return cust.id, contract.id


def test_audit_clean_when_cache_matches(client):
    with client.application.app_context():
        _, contract_id = _seed_contract()
        contract = db.session.get(Contract, contract_id)
        refresh_contract_cache(contract)
        db.session.commit()

    with client.application.app_context():
        audit = audit_billing_consistency()
        contract_issues = [i for i in audit['issues'] if i['entity'] == 'contract' and i['id'] == contract_id]
        assert contract_issues == []


def test_repair_fixes_stale_contract_paid_amount(client):
    with client.application.app_context():
        cid, contract_id = _seed_contract()
        inv = Invoice(
            code='INV-BC01',
            invoice_type='فاتورة ضريبية',
            customer_id=cid,
            contract_id=contract_id,
            invoice_date=date.today(),
            amount=10000,
            tax_amount=1500,
            total=11500,
            paid_amount=5000,
            status='مدفوع جزئياً',
        )
        db.session.add(inv)
        db.session.flush()
        rev = Revenue(
            code='REV-BC01',
            customer_id=cid,
            contract_id=contract_id,
            invoice_id=inv.id,
            revenue_date=date.today(),
            revenue_type='تحصيل فاتورة',
            amount=4347.83,
            tax_amount=652.17,
            total=5000,
            status='محصّل',
        )
        db.session.add(rev)
        contract = db.session.get(Contract, contract_id)
        contract.paid_amount = 0
        db.session.commit()

    with client.application.app_context():
        audit = audit_billing_consistency()
        assert audit['issue_count'] >= 1

    with client.application.app_context():
        result = repair_billing_consistency(commit=True)
        assert result['contracts_updated'] >= 1
        contract = db.session.get(Contract, contract_id)
        assert contract.paid_amount == 5000

    with client.application.app_context():
        assert audit_billing_consistency()['ok'] is True


def test_revenue_paid_for_invoice_sums_collected(client):
    with client.application.app_context():
        cid, contract_id = _seed_contract()
        inv = Invoice(
            code='INV-BC02',
            customer_id=cid,
            contract_id=contract_id,
            invoice_date=date.today(),
            amount=3000,
            total=3000,
            paid_amount=0,
        )
        db.session.add(inv)
        db.session.flush()
        db.session.add(Revenue(
            code='REV-BC02',
            customer_id=cid,
            contract_id=contract_id,
            invoice_id=inv.id,
            revenue_date=date.today(),
            revenue_type='تحصيل',
            amount=3000,
            total=3000,
            status='محصّل',
        ))
        db.session.commit()
        inv_id = inv.id

    with client.application.app_context():
        assert revenue_paid_for_invoice(inv_id) == 3000


def test_admin_consistency_api_requires_admin(client):
    login_as(client, 'viewer')
    r = client.get('/api/admin/billing/consistency')
    assert r.status_code == 403


def test_admin_consistency_api_admin(client):
    login_as(client, 'admin')
    r = client.get('/api/admin/billing/consistency')
    assert r.status_code == 200
    data = r.get_json()
    assert 'issue_count' in data
    assert 'ok' in data
