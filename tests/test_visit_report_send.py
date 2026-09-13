"""إرسال محضر صيانة للعميل — واتساب + PDF."""
import json
from datetime import date

from models import Customer, Elevator, MaintenanceVisit, Technician, db
from operations import build_visit_report_customer_message, visit_report_customer_whatsapp
from tests.conftest import ensure_test_organization, login_as


def _seed_visit(*, phone='0555123456', with_report=True):
    oid = ensure_test_organization()
    tech = Technician(organization_id=oid, code='T-VS', name='فني محضر', phone='0501111111')
    db.session.add(tech)
    cust = Customer(
        organization_id=oid,
        code='C-VS',
        name='عميل محضر',
        phone=phone,
        status='نشط',
    )
    db.session.add(cust)
    db.session.flush()
    elev = Elevator(organization_id=oid, code='E-VS', customer_id=cust.id, status='نشط')
    db.session.add(elev)
    db.session.flush()
    checklist = ''
    if with_report:
        checklist = json.dumps({
            'template_key': 'liftcore_standard_v1',
            'items': {'1_0': {'status': 'ok', 'note': ''}},
            'meta': {},
        }, ensure_ascii=False)
    visit = MaintenanceVisit(
        organization_id=oid,
        code='V-VS1',
        elevator_id=elev.id,
        technician_id=tech.id,
        visit_date=date.today(),
        status='مكتملة',
        checklist_json=checklist,
    )
    db.session.add(visit)
    db.session.commit()
    return visit.id


def test_visit_report_whatsapp_requires_phone(client):
    with client.application.app_context():
        visit_id = _seed_visit(phone='')
        result = visit_report_customer_whatsapp(visit_id, 'https://app.test/')
        assert result['ok'] is False
        assert 'جوال' in result['error']


def test_visit_report_whatsapp_requires_filled_report(client):
    with client.application.app_context():
        visit_id = _seed_visit(with_report=False)
        result = visit_report_customer_whatsapp(visit_id, 'https://app.test/')
        assert result['ok'] is False
        assert 'المحضر' in result['error']


def test_visit_report_whatsapp_ok(client):
    with client.application.app_context():
        visit_id = _seed_visit()
        result = visit_report_customer_whatsapp(visit_id, 'https://app.test/')
        assert result['ok'] is True
        assert 'wa.me' in result['url']
        assert 'report?print=1' in result['report_url']


def test_visit_report_message_includes_pdf_link(client):
    with client.application.app_context():
        visit_id = _seed_visit()
        visit = db.session.get(MaintenanceVisit, visit_id)
        msg = build_visit_report_customer_message(
            visit,
            report_url='https://app.test/maintenance-visits/1/report?print=1',
            company_name='LiftCore Test',
        )
        assert 'محضر صيانة' in msg
        assert 'PDF' in msg
        assert visit.code in msg


def test_visit_report_customer_send_api(client):
    login_as(client, 'admin')
    with client.application.app_context():
        visit_id = _seed_visit()
    r = client.post(f'/api/maintenance-visits/{visit_id}/customer-report-send')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    assert data['report_print_path'].endswith('/report?print=1')
