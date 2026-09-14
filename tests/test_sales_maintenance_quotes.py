"""اختبارات مسار عروض صيانة المبيعات."""
from datetime import date

from models import Contract, Customer, MaintenanceQuote, db
from sales.service import (
    apply_total_including_tax,
    create_contract_from_maintenance_quote,
    money_round,
    recalc_quote_totals,
)
from tenant_scope import assign_organization, tenant_query


def test_recalc_quote_totals():
    q = MaintenanceQuote(value=1000, tax_pct=15)
    recalc_quote_totals(q)
    assert money_round(q.tax_amount) == 150
    assert money_round(q.total) == 1150


def test_apply_total_including_tax():
    q = MaintenanceQuote(tax_pct=15)
    apply_total_including_tax(q, 1150)
    assert money_round(q.total) == 1150
    assert money_round(q.value) == 1000
    assert money_round(q.tax_amount) == 150


def test_maintenance_quote_print_page(client):
    from models import Elevator

    login_as = __import__('tests.conftest', fromlist=['login_as']).login_as
    login_as(client, 'admin')
    with client.application.app_context():
        cust = Customer(code='C-9003', name='عميل طباعة صيانة', status='نشط')
        assign_organization(cust)
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(code='EL-9003', customer_id=cust.id, status='نشط')
        assign_organization(elev)
        db.session.add(elev)
        db.session.flush()
        quote = MaintenanceQuote(
            code='MQ-90003',
            customer_id=cust.id,
            status='مسودة',
            duration_months=12,
            maint_frequency='شهري',
            visits_per_month=1,
            tax_pct=15,
            notes='باقة الخدمة: قياسي\nنطاق الخدمة: زيارات وقائية، فحص سلامة',
        )
        assign_organization(quote)
        apply_total_including_tax(quote, 2300)
        db.session.add(quote)
        db.session.commit()
        qid = quote.id

    r = client.get(f'/sales/maintenance-quotes/{qid}/print')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'MQ-90003' in html
    assert '2,300.00' in html
    assert 'قياسي' in html
    assert 'عرض سعر — عقد صيانة مصاعد' in html
    assert 'mq-stats' in html
    assert 'sheet-top' in html
    assert 'q-sign-box' in html
    assert 'document-company-seal.css' in html
    assert 'طباعة / PDF' in html


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


def test_estimate_converts_to_install_quote(client):
    from installation.models import InstallProject, InstallQuotation
    from installation.routes import _next_code
    from models import ElevatorEstimate, ElevatorEstimateLine
    from sales.service import create_install_project_and_quote_from_estimate

    with client.application.app_context():
        cust = Customer(code='C-9002', name='عميل تقدير', status='نشط')
        assign_organization(cust)
        db.session.add(cust)
        db.session.flush()

        est = ElevatorEstimate(
            code='ES-9001',
            customer_id=cust.id,
            project_name='برج اختبار',
            city='مكة المكرمة',
            cost_subtotal=100000,
            margin_pct=12,
            margin_amount=12000,
            subtotal=112000,
            vat_pct=15,
            vat_amount=16800,
            total=128800,
            status='معتمد',
        )
        assign_organization(est)
        db.session.add(est)
        db.session.flush()
        line = ElevatorEstimateLine(
            estimate_id=est.id,
            category='ماكينة',
            description='ماكينة جر',
            quantity=1,
            unit='وحدة',
            unit_price=100000,
            line_total=100000,
        )
        assign_organization(line)
        db.session.add(line)
        db.session.commit()
        eid = est.id

        est = db.session.get(ElevatorEstimate, eid)
        result = create_install_project_and_quote_from_estimate(
            est,
            next_project_code_fn=_next_code,
            next_quote_code_fn=_next_code,
        )
        db.session.commit()

        assert result['created'] is True
        project = db.session.get(InstallProject, result['project_id'])
        quote = db.session.get(InstallQuotation, result['quotation_id'])
        assert project is not None
        assert quote is not None
        assert project.customer_id == cust.id
        assert quote.grand_total == money_round(128800)
        assert est.status == 'محوّل لعرض سعر'
        assert est.result_project_id == project.id
        assert len(quote.lines) == 1


def test_sales_hub_requires_login(client):
    r = client.get('/sales/', follow_redirects=False)
    assert r.status_code in (302, 303, 401)


def test_delete_maintenance_quote(client):
    login_as = __import__('tests.conftest', fromlist=['login_as']).login_as
    login_as(client, 'admin')
    with client.application.app_context():
        from tests.conftest import ensure_test_organization

        oid = ensure_test_organization()
        cust = Customer(organization_id=oid, code='C-DEL', name='حذف', status='نشط')
        db.session.add(cust)
        db.session.flush()
        quote = MaintenanceQuote(code='MQ-DEL1', customer_id=cust.id, status='مسودة')
        assign_organization(quote)
        apply_total_including_tax(quote, 1000)
        db.session.add(quote)
        db.session.commit()
        qid = quote.id

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    r = client.post(
        f'/sales/maintenance-quotes/{qid}/delete',
        data={'csrf_token': 'test-csrf'},
        follow_redirects=True,
    )
    assert r.status_code == 200
    with client.application.app_context():
        assert db.session.get(MaintenanceQuote, qid) is None


def test_clear_all_maintenance_quotes(client):
    login_as = __import__('tests.conftest', fromlist=['login_as']).login_as
    login_as(client, 'admin')
    with client.application.app_context():
        from tests.conftest import ensure_test_organization

        oid = ensure_test_organization()
        cust = Customer(organization_id=oid, code='C-CLR', name='تصفير', status='نشط')
        db.session.add(cust)
        db.session.flush()
        for i in range(2):
            q = MaintenanceQuote(code=f'MQ-CLR{i}', customer_id=cust.id, status='مسودة')
            assign_organization(q)
            apply_total_including_tax(q, 500)
            db.session.add(q)
        db.session.commit()

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    r = client.post(
        '/sales/maintenance-quotes/clear-all',
        data={'csrf_token': 'test-csrf', 'confirm': 'CLEAR_MQ'},
        follow_redirects=True,
    )
    assert r.status_code == 200
    with client.application.app_context():
        assert tenant_query(MaintenanceQuote).count() == 0
