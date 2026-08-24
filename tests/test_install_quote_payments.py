"""دفعات عرض التركيب: دفعتان أو ثلاث."""
from installation.models import InstallProject, InstallQuotation, InstallTimelineStep
from installation.project_card import ensure_project_card_schema
from models import Customer, Organization, db
from tests.conftest import login_as


def test_payment_items_two_installments(client):
    with client.application.app_context():
        q = InstallQuotation(
            pay_advance_pct=70,
            pay_supply_pct=0,
            pay_final_pct=30,
            grand_total=10000,
        )
        assert q.payment_count() == 2
        items = q.payment_items()
        assert [it['label'] for it in items] == ['دفعة مقدمة', 'عند التسليم']
        assert items[0]['amount'] == 7000
        assert items[1]['amount'] == 3000


def test_payment_items_three_installments(client):
    with client.application.app_context():
        q = InstallQuotation(
            pay_advance_pct=50,
            pay_supply_pct=40,
            pay_final_pct=10,
            grand_total=10000,
        )
        assert q.payment_count() == 3
        items = q.payment_items()
        assert [it['label'] for it in items] == ['دفعة مقدمة', 'عند التوريد', 'دفعة نهائية']


def test_two_payment_quote_skips_supply_timeline_step(client):
    login_as(client, role='admin')
    with client.application.app_context():
        ensure_project_card_schema()
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-PAY2',
            name='عميل دفعتين',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-PAY2',
            title='مشروع دفعتين',
            status='عرض سعر',
            customer_id=cust.id,
        )
        db.session.add(project)
        db.session.flush()
        q = InstallQuotation(
            organization_id=org.id,
            code='QT-PAY2',
            project_id=project.id,
            customer_id=cust.id,
            quote_type='new',
            status='مُرسل',
            grand_total=80000,
            before_tax=69565,
            vat_amount=10435,
            pay_advance_pct=50,
            pay_supply_pct=0,
            pay_final_pct=50,
        )
        db.session.add(q)
        db.session.commit()
        pid, qid = project.id, q.id
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-csrf'

    resp = client.post(
        f'/installation/projects/{pid}/quotes/{qid}/approve',
        data={'csrf_token': 'test-csrf'},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    with client.application.app_context():
        steps = InstallTimelineStep.query.filter_by(project_id=pid).all()
        keys = {s.step_key for s in steps}
        assert 'advance_payment' in keys
        assert 'payment_final' in keys
        assert 'payment_on_delivery' not in keys
