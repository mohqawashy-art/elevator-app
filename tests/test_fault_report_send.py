"""إرسال تقرير عطل للعميل — واتساب."""
import json

from models import Customer, Elevator, Fault, Technician, db
from operations import build_fault_report_customer_message, fault_report_customer_whatsapp
from tests.conftest import ensure_test_organization, login_as


def _seed_fault(*, phone='0555123456', with_report=True, building='برج النور'):
    oid = ensure_test_organization()
    tech = Technician(organization_id=oid, code='T-FRS', name='فني عطل', phone='0501111111')
    db.session.add(tech)
    cust = Customer(
        organization_id=oid,
        code='C-FRS',
        name='عميل عطل',
        phone=phone,
        status='نشط',
    )
    db.session.add(cust)
    db.session.flush()
    elev = Elevator(
        organization_id=oid,
        code='E-FRS',
        customer_id=cust.id,
        status='نشط',
        building_name=building,
    )
    db.session.add(elev)
    db.session.flush()
    report = ''
    if with_report:
        report = json.dumps({
            'meta': {'diagnosis': 'كونتاكتور', 'action_taken': 'استبدال', 'visit_outcome': 'solved'},
            'parts': [],
        }, ensure_ascii=False)
    fault = Fault(
        organization_id=oid,
        code='FA-FRS1',
        elevator_id=elev.id,
        technician_id=tech.id,
        fault_type='كهرباء',
        status='تم الاصلاح',
        report_json=report,
    )
    db.session.add(fault)
    db.session.commit()
    return fault.id


def test_fault_report_whatsapp_requires_phone(client):
    with client.application.app_context():
        fault_id = _seed_fault(phone='')
        result = fault_report_customer_whatsapp(fault_id, 'https://app.test/')
        assert result['ok'] is False
        assert 'جوال' in result['error']


def test_fault_report_whatsapp_requires_filled_report(client):
    with client.application.app_context():
        fault_id = _seed_fault(with_report=False)
        result = fault_report_customer_whatsapp(fault_id, 'https://app.test/')
        assert result['ok'] is False
        assert 'التقرير' in result['error']


def test_fault_report_whatsapp_ok(client):
    with client.application.app_context():
        fault_id = _seed_fault()
        result = fault_report_customer_whatsapp(fault_id, 'https://app.test/')
        assert result['ok'] is True
        assert 'wa.me' in result['url']
        assert '/r/fault/' in result['report_url']
        msg = build_fault_report_customer_message(
            db.session.get(Fault, fault_id),
            report_url=result['report_url'],
            company_name='LiftCore',
        )
        assert 'برج النور' in msg


def test_fault_report_send_api(client):
    login_as(client, 'admin')
    with client.application.app_context():
        fault_id = _seed_fault()
    resp = client.post(f'/api/faults/{fault_id}/customer-report-send')
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['ok'] is True
    assert 'wa.me' in data['url']
    page = client.get(f'/faults/{fault_id}/report')
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert 'إرسال التقرير (واتساب)' in html
    assert 'برج النور' in html
    assert 'LiftCoreFaultReportSend.send' in html


def test_faults_report_rows_include_building(client):
    from report_data import get_report_faults

    with client.application.app_context():
        _seed_fault(building='مجمع التقرير')
        rows = get_report_faults(db, Fault)
    assert any(r.get('building') == 'مجمع التقرير' for r in rows)


def test_faults_list_includes_building_name(client):
    from app import _faults_js_list

    with client.application.app_context():
        fault_id = _seed_fault(building='مجمع الأندلس')
        fault = db.session.get(Fault, fault_id)
        rows = _faults_js_list([fault])
        assert rows[0]['building'] == 'مجمع الأندلس'
