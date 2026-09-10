"""P2 K1 — smoke بوابة الفني."""
from __future__ import annotations

from datetime import date, datetime

from models import Customer, Elevator, Fault, MaintenanceVisit, Technician, db
from operations import _field_alert_stamp, field_technician_payload

from tests.conftest import ensure_test_organization, login_as


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


def test_field_session_can_poll_live_revision(client):
    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(organization_id=oid, code='T-REV2', name='فني', phone='0500000088', team='أعطال', status='متاح')
        db.session.add(tech)
        db.session.commit()
        tech_id = tech.id
    with client.session_transaction() as sess:
        sess['field_tech_id'] = tech_id
    r = client.get('/api/live/revision')
    assert r.status_code == 200
    assert 'revision' in (r.get_json() or {})


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


def test_fault_add_appears_on_field_portal(client):
    """عطل جديد من المكتب يظهر فوراً في بوابة الفني المكلّف."""
    from werkzeug.security import generate_password_hash

    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(
            organization_id=oid,
            code='T-FP1',
            name='فني بوابة',
            phone='0503334455',
            team='صيانة',
            status='متاح',
            sign_pin_hash=generate_password_hash('123456'),
        )
        db.session.add(tech)
        cust = Customer(organization_id=oid, code='C-FP1', name='عميل بوابة', status='نشط')
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-FP1', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.commit()
        tech_id, elev_id = tech.id, elev.id

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    r = client.post(
        '/faults/add',
        data={
            'csrf_token': 'test-csrf',
            'elevator_id': str(elev_id),
            'technician_ids': str(tech_id),
            'technician_id': str(tech_id),
            'fault_type': 'توقف',
            'priority': 'عاجلة',
            'client_report': 'المصعد واقف',
            'billable': 'no',
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    with client.session_transaction() as sess:
        sess['field_tech_id'] = tech_id

    home = client.get('/field')
    assert home.status_code == 200
    html = home.get_data(as_text=True)
    assert 'أعطال مكلّفة' in html or 'الأعطال المفتوحة' in html

    api = client.get('/api/field/me')
    assert api.status_code == 200
    payload = api.get_json()
    assert payload.get('ok') is True
    assert any(f.get('fault_type') == 'توقف' for f in payload.get('faults') or [])


def test_fault_add_bumps_live_revision(client):
    from live_sync import get_live_revision

    login_as(client, 'admin')
    with client.application.app_context():
        rev_before = get_live_revision()
        oid = ensure_test_organization()
        tech = Technician(organization_id=oid, code='T-REV', name='فني', phone='0500000077', team='أعطال', status='متاح')
        db.session.add(tech)
        cust = Customer(organization_id=oid, code='C-REV', name='عميل', status='نشط')
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-REV', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.commit()
        tech_id, elev_id = tech.id, elev.id

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    client.post(
        '/faults/add',
        data={
            'csrf_token': 'test-csrf',
            'elevator_id': str(elev_id),
            'technician_ids': str(tech_id),
            'technician_id': str(tech_id),
            'fault_type': 'توقف',
            'priority': 'عاجلة',
            'client_report': 'اختبار',
            'billable': 'no',
        },
        follow_redirects=True,
    )
    with client.application.app_context():
        assert get_live_revision() > rev_before


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


def test_closed_fault_fault_visit_hidden_from_field_portal(client):
    """زيارة نوع عطل لعطل مغلق لا تظهر في بوابة الفني."""
    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(
            organization_id=oid,
            code='T-FV',
            name='فني زيارة عطل',
            phone='0500000091',
            team='صيانة',
        )
        db.session.add(tech)
        db.session.flush()
        cust = Customer(organization_id=oid, code='C-FV', name='عميل زيارة عطل', status='نشط')
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-FV', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()
        fault = Fault(
            organization_id=oid,
            code='F-FV1',
            elevator_id=elev.id,
            technician_id=tech.id,
            status='تم الاصلاح',
            resolution='أُغلق من المكتب',
            priority='عادية',
            reported_at=datetime.utcnow(),
            resolved_at=datetime.utcnow(),
        )
        visit = MaintenanceVisit(
            organization_id=oid,
            code='V-FV1',
            elevator_id=elev.id,
            technician_id=tech.id,
            visit_date=date.today(),
            visit_type='عطل — توقف',
            status='مُرسلة للفني',
            fault_id=None,
        )
        db.session.add_all([fault, visit])
        db.session.commit()
        payload = field_technician_payload(tech.id, portal_kind='both')
        assert not any(v['code'] == visit.code for v in payload.get('visits_today') or [])
        assert not any(f['code'] == fault.code for f in payload.get('faults') or [])


def test_field_visit_page_sets_at_client_status(client):
    from operations import VISIT_AT_CLIENT, VISIT_FINISHED_AT_CLIENT

    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(organization_id=oid, code='T-VST', name='فني زيارة', phone='0501112233', team='صيانة')
        db.session.add(tech)
        cust = Customer(organization_id=oid, code='C-VST', name='عميل زيارة', status='نشط')
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-VST', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()
        visit = MaintenanceVisit(
            organization_id=oid,
            code='V-VST1',
            elevator_id=elev.id,
            technician_id=tech.id,
            visit_date=date.today(),
            status='مُرسلة للفني',
        )
        db.session.add(visit)
        db.session.commit()
        visit_id, tech_id = visit.id, tech.id

    with client.session_transaction() as sess:
        sess['field_tech_id'] = tech_id

    r = client.get(f'/field/visit/{visit_id}')
    assert r.status_code == 200

    with client.application.app_context():
        v = db.session.get(MaintenanceVisit, visit_id)
        assert v.status == VISIT_AT_CLIENT

    fin = client.post(
        f'/api/maintenance-visits/{visit_id}/report',
        json={'mark_finished_at_client': True},
    )
    assert fin.status_code == 200
    assert fin.get_json().get('ok') is True

    with client.application.app_context():
        v = db.session.get(MaintenanceVisit, visit_id)
        assert v.status == VISIT_FINISHED_AT_CLIENT


def test_field_geofence_blocks_far_visit(client):
    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(organization_id=oid, code='T-GEO', name='فني موقع', phone='0502223344', team='صيانة')
        db.session.add(tech)
        cust = Customer(
            organization_id=oid,
            code='C-GEO',
            name='عميل موقع',
            status='نشط',
            lat='24.713600',
            lng='46.675300',
        )
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-GEO', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()
        visit = MaintenanceVisit(
            organization_id=oid,
            code='V-GEO1',
            elevator_id=elev.id,
            technician_id=tech.id,
            visit_date=date.today(),
            status='مُرسلة للفني',
        )
        db.session.add(visit)
        db.session.commit()
        visit_id, tech_id = visit.id, tech.id

    with client.session_transaction() as sess:
        sess['field_tech_id'] = tech_id

    r = client.get(f'/field/visit/{visit_id}?lat=24.800000&lng=46.675300')
    assert r.status_code == 403
    assert 'بعيد' in r.get_data(as_text=True)

    api = client.get(
        '/api/field/verify-proximity',
        query_string={'kind': 'visit', 'id': visit_id, 'lat': 24.800000, 'lng': 46.675300},
    )
    assert api.status_code == 403
    assert api.get_json().get('code') == 'too_far'


def test_field_geofence_allows_near_visit(client):
    from operations import VISIT_AT_CLIENT

    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(organization_id=oid, code='T-GEO2', name='فني قريب', phone='0502223355', team='صيانة')
        db.session.add(tech)
        cust = Customer(
            organization_id=oid,
            code='C-GEO2',
            name='عميل قريب',
            status='نشط',
            lat='24.713600',
            lng='46.675300',
        )
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-GEO2', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()
        visit = MaintenanceVisit(
            organization_id=oid,
            code='V-GEO2',
            elevator_id=elev.id,
            technician_id=tech.id,
            visit_date=date.today(),
            status='مُرسلة للفني',
        )
        db.session.add(visit)
        db.session.commit()
        visit_id, tech_id = visit.id, tech.id

    with client.session_transaction() as sess:
        sess['field_tech_id'] = tech_id

    r = client.get(f'/field/visit/{visit_id}?lat=24.713650&lng=46.675350')
    assert r.status_code == 200

    with client.application.app_context():
        v = db.session.get(MaintenanceVisit, visit_id)
        assert v.status == VISIT_AT_CLIENT


def test_field_geofence_blocks_far_fault(client):
    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(organization_id=oid, code='T-GF', name='فني عطل', phone='0503334455', team='أعطال')
        db.session.add(tech)
        cust = Customer(
            organization_id=oid,
            code='C-GF',
            name='عميل عطل',
            status='نشط',
            lat='24.713600',
            lng='46.675300',
        )
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-GF', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()
        fault = Fault(
            organization_id=oid,
            code='F-GF1',
            elevator_id=elev.id,
            technician_id=tech.id,
            status='مفتوح',
            priority='عادية',
            reported_at=datetime.utcnow(),
        )
        db.session.add(fault)
        db.session.commit()
        fault_id, tech_id = fault.id, tech.id

    with client.session_transaction() as sess:
        sess['field_tech_id'] = tech_id

    r = client.get(f'/field/fault/{fault_id}?lat=24.800000&lng=46.675300')
    assert r.status_code == 403
