"""اختبار قبول عرض السعر وبدء التنفيذ."""
from datetime import date

from installation.models import InstallProject, InstallQuotation, InstallTimelineStep
from installation.project_card import ensure_project_card_schema
from models import Customer, Organization, db
from tests.conftest import login_as


def test_quote_approve_starts_execution(client):
    login_as(client, role='admin')
    with client.application.app_context():
        ensure_project_card_schema()
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-APPR1',
            name='عميل قبول',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-APPR1',
            title='مشروع قبول',
            status='عرض سعر',
            customer_id=cust.id,
        )
        db.session.add(project)
        db.session.flush()
        q = InstallQuotation(
            organization_id=org.id,
            code='QT-APPR1',
            project_id=project.id,
            customer_id=cust.id,
            quote_type='new',
            status='مُرسل',
            grand_total=115000,
            before_tax=100000,
            vat_amount=15000,
            pay_advance_pct=50,
            pay_supply_pct=40,
            pay_final_pct=10,
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
    assert resp.status_code in (302, 303), resp.data.decode('utf-8', errors='ignore')[:500]
    loc = resp.headers.get('Location', '')
    assert f'/installation/projects/{pid}/execution' in loc

    with client.application.app_context():
        p = db.session.get(InstallProject, pid)
        assert p.accepted_quotation_id == qid
        assert p.execution_started_at is not None
        assert p.status == 'عقد'
        steps = InstallTimelineStep.query.filter_by(project_id=pid).all()
        assert len(steps) >= 10
        assert any(s.status == 'جاري' for s in steps)

    page = client.get(f'/installation/projects/{pid}/execution')
    assert page.status_code == 200
    body = page.data.decode('utf-8', errors='ignore')
    assert 'التنفيذ' in body or 'المهمة الحالية' in body
