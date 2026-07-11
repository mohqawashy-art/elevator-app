"""P2 K1 — smoke بوابة الفني."""
from __future__ import annotations

from datetime import date, datetime

from models import Customer, Elevator, Fault, MaintenanceVisit, Technician, db
from operations import _field_alert_stamp, field_technician_payload

from tests.conftest import ensure_test_organization


def test_field_login_page_loads(client):
    r = client.get('/field/login')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'field' in html.lower() or 'فني' in html or 'PIN' in html


def test_field_home_redirects_without_session(client):
    r = client.get('/field', follow_redirects=False)
    assert r.status_code in (302, 401, 403)


def test_field_api_me_requires_auth(client):
    r = client.get('/api/field/me')
    assert r.status_code in (401, 403)


def test_field_payload_includes_alert_stamp(client):
    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(
            organization_id=oid,
            code='T-AL',
            name='فني تنبيه',
            phone='0500000099',
            team='صيانة',
        )
        db.session.add(tech)
        db.session.flush()
        cust = Customer(organization_id=oid, code='C-AL', name='عميل تنبيه', status='نشط')
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-AL', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()
        visit = MaintenanceVisit(
            organization_id=oid,
            code='V-AL1',
            elevator_id=elev.id,
            technician_id=tech.id,
            visit_date=date.today(),
            status='مُرسلة للفني',
            dispatched_at=datetime.utcnow(),
        )
        fault = Fault(
            organization_id=oid,
            code='F-AL1',
            elevator_id=elev.id,
            technician_id=tech.id,
            status='قيد المعالجة',
            priority='عالية',
            fault_type='توقف',
            dispatched_at=datetime.utcnow(),
            reported_at=datetime.utcnow(),
        )
        db.session.add_all([visit, fault])
        db.session.commit()
        payload = field_technician_payload(tech.id, portal_kind='both')
        assert 'alert_stamp' in payload
        assert payload['alert_stamp']
        assert any(v['id'] == visit.id for v in payload['visits'])
        assert any(f['id'] == fault.id for f in payload['faults'])
        assert payload['visits'][0].get('dispatched_at')
        stamp2 = _field_alert_stamp([visit], [fault])
        assert stamp2 == payload['alert_stamp']


def test_field_faults_team_sees_unassigned_open_faults(client):
    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(
            organization_id=oid,
            code='T-UF',
            name='فني أعطال',
            phone='0500000088',
            team='أعطال',
        )
        db.session.add(tech)
        db.session.flush()
        cust = Customer(organization_id=oid, code='C-UF', name='عميل بلا تعيين', status='نشط')
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-UF', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()
        fault = Fault(
            organization_id=oid,
            code='F-UF1',
            elevator_id=elev.id,
            technician_id=None,
            status='مفتوح',
            priority='عاجلة',
            reported_at=datetime.utcnow(),
        )
        db.session.add(fault)
        db.session.commit()
        payload = field_technician_payload(tech.id, portal_kind='faults')
        assert any(f['id'] == fault.id for f in payload['faults'])
        assert any(f.get('unassigned') for f in payload['faults'] if f['id'] == fault.id)
