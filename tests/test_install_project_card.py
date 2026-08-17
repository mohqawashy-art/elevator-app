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
