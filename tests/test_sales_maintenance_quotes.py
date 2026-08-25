"""اختبارات مسار عروض صيانة المبيعات."""
from datetime import date

from models import Contract, Customer, MaintenanceQuote, db
from sales.service import create_contract_from_maintenance_quote, money_round, recalc_quote_totals
from tenant_scope import assign_organization


def test_recalc_quote_totals():
    q = MaintenanceQuote(value=1000, tax_pct=15)
    recalc_quote_totals(q)
    assert money_round(q.tax_amount) == 150
    assert money_round(q.total) == 1150


def test_approve_maintenance_quote_creates_contract(client):
    from app import next_code

    with client.application.app_context():
        cust = Customer(code='C-9001', name='عميل اختبار مبيعات', status='نشط')
        assign_organization(cust)
        db.session.add(cust)
        db.session.flush()

        quote = MaintenanceQuote(
            code='MQ-90001',
            customer_id=cust.id,
            status='مُرسل',
            duration_months=12,
            maint_frequency='شهري',
            visits_per_month=1,
            value=2000,
            tax_pct=15,
            start_date=date.today(),
            city='مكة المكرمة',
        )
        assign_organization(quote)
        recalc_quote_totals(quote)
        db.session.add(quote)
        db.session.commit()
        qid = quote.id

        q = db.session.get(MaintenanceQuote, qid)
        contract = create_contract_from_maintenance_quote(q, next_code_fn=next_code)
        db.session.commit()

        assert contract.code.startswith('CN-')
        assert contract.contract_type == 'عقد صيانة'
        assert money_round(contract.total) == money_round(q.total)
        assert q.status == 'مقبول'
        assert q.result_contract_id == contract.id
        assert db.session.get(Contract, contract.id) is not None


def test_sales_hub_requires_login(client):
    r = client.get('/sales/', follow_redirects=False)
    assert r.status_code in (302, 303, 401)
