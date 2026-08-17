"""اختبارات كارت مشروع التركيب."""
from datetime import date

from sqlalchemy import text

from installation.models import InstallLead, InstallProject, InstallProjectCostItem, InstallProjectReceipt
from installation.project_card import build_project_card, ensure_project_card_schema
from models import Organization, db
from tests.conftest import login_as


def test_leads_list_recovers_missing_contract_value(client):
    """قائمة الفرص كانت تفشل 500 إذا غاب contract_value عن installation_projects."""
    login_as(client, role='admin')
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        lead = InstallLead(
            organization_id=org.id,
            code='LD-MISSCOL',
            client_name='عميل اختبار',
            status='جديد',
        )
        db.session.add(lead)
        db.session.commit()
        # محاكاة إنتاج بلا عمود القيمة
        try:
            db.session.execute(text('ALTER TABLE installation_projects DROP COLUMN contract_value'))
            db.session.commit()
        except Exception:
            db.session.rollback()
        import installation.routes as install_routes
        install_routes._schema_ensured = False

    resp = client.get('/installation/leads')
    assert resp.status_code == 200
    assert 'فرص البيع' in resp.data.decode('utf-8', errors='ignore')


def test_leads_add_creates_opportunity(client):
    login_as(client, role='admin')
    with client.application.app_context():
        from models import Customer
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-LEADADD',
            name='عميل فرصة',
            status='نشط',
            phone='0500000000',
        )
        db.session.add(cust)
        db.session.commit()
        cid = cust.id
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-csrf'

    resp = client.post('/installation/leads/add', data={
        'csrf_token': 'test-csrf',
        'customer_id': cid,
        'source': 'اتصال',
        'status': 'جديد',
    }, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode('utf-8', errors='ignore')
    assert 'تم إنشاء الفرصة' in body or 'LD-' in body


def test_two_orgs_can_reuse_lead_code(client):
    """قيود code العالمية كانت تمنع LD-0001 لمستأجر ثانٍ."""
    from installation.schema import ensure_install_tenant_uniques

    login_as(client, role='admin')
    with client.application.app_context():
        ensure_install_tenant_uniques()
        org_a = Organization.query.filter_by(slug='default').first()
        org_b = Organization.query.filter_by(slug='beta').first()
        if not org_b:
            org_b = Organization(slug='beta', name='Beta', status='active')
            db.session.add(org_b)
            db.session.commit()

        for org in (org_a, org_b):
            existing = (
                InstallLead.query.execution_options(skip_tenant=True)
                .filter_by(organization_id=org.id, code='LD-0001')
                .first()
            )
            if existing:
                db.session.delete(existing)
        db.session.commit()

        db.session.add(InstallLead(
            organization_id=org_a.id,
            code='LD-0001',
            client_name='عميل أ',
            status='جديد',
        ))
        db.session.commit()
        db.session.add(InstallLead(
            organization_id=org_b.id,
            code='LD-0001',
            client_name='عميل مستأجر آخر',
            status='جديد',
        ))
        db.session.commit()
        total = (
            InstallLead.query.execution_options(skip_tenant=True)
            .filter_by(code='LD-0001')
            .count()
        )
        assert total >= 2


def test_project_card_costs_and_receipts(client):
    login_as(client, role='admin')
    with client.application.app_context():
        ensure_project_card_schema()
        org = Organization.query.filter_by(slug='default').first()
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-CARD1',
            title='مشروع كارت',
            status='عقد',
            contract_value=100000,
        )
        db.session.add(project)
        db.session.flush()
        db.session.add(InstallProjectCostItem(
            organization_id=org.id,
            project_id=project.id,
            category='قطع غيار',
            title='سكك',
            amount=15000,
            cost_date=date.today(),
        ))
        db.session.add(InstallProjectCostItem(
            organization_id=org.id,
            project_id=project.id,
            category='عمالة',
            title='دفعة عمالة 1',
            amount=8000,
            installment_no=1,
            cost_date=date.today(),
        ))
        db.session.add(InstallProjectReceipt(
            organization_id=org.id,
            project_id=project.id,
            installment_no=1,
            label='دفعة رقم 1',
            amount=40000,
            status='مستلمة',
            received_date=date.today(),
        ))
        db.session.commit()
        pid = project.id

        card = build_project_card(db.session.get(InstallProject, pid))
        assert card['contract_value'] == 100000
        assert card['total_cost'] == 23000
        assert card['received'] == 40000
        assert card['client_remaining'] == 60000
        assert card['profit'] == 77000
        assert len(card['cost_groups']) == 2

    resp = client.get(f'/installation/projects/{pid}')
    assert resp.status_code == 200
    body = resp.data.decode('utf-8', errors='ignore')
    assert 'كارت المشروع' in body
    assert 'دفعة رقم 1' in body
    assert 'سكك' in body
