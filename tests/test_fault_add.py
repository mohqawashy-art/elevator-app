"""تسجيل عطل من المكتب."""
from __future__ import annotations

from models import Customer, Elevator, Fault, FaultTechnician, Technician, db
from tests.conftest import login_as


def test_fault_add_creates_record(client):
    login_as(client, 'admin')
    with client.application.app_context():
        from tests.conftest import ensure_test_organization
        oid = ensure_test_organization()
        tech = Technician(
            organization_id=oid,
            code='T-F1',
            name='فني أعطال',
            phone='0501112233',
            team='صيانة',
            status='متاح',
        )
        db.session.add(tech)
        cust = Customer(organization_id=oid, code='C-F1', name='عميل عطل', status='نشط')
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-F1', customer_id=cust.id, status='نشط')
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
            'fault_type': 'توقف مفاجئ',
            'priority': 'عالية',
            'client_report': 'المصعد واقف',
            'billable': 'no',
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    with client.application.app_context():
        faults = Fault.query.order_by(Fault.id.desc()).all()
        assert len(faults) >= 1
        f = faults[0]
        assert f.technician_id == tech_id
        assert f.organization_id is not None
        assert FaultTechnician.query.filter_by(fault_id=f.id).count() == 1
        assert f.status in ('مفتوح', 'قيد المعالجة')
        assert f.dispatched_at is not None


def test_fault_add_json_returns_whatsapp_url(client):
    login_as(client, 'admin')
    with client.application.app_context():
        from tests.conftest import ensure_test_organization
        oid = ensure_test_organization()
        tech = Technician(
            organization_id=oid,
            code='T-F2',
            name='فني واتساب',
            phone='0502223344',
            team='أعطال',
            status='متاح',
        )
        db.session.add(tech)
        cust = Customer(organization_id=oid, code='C-F2', name='عميل 2', status='نشط')
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-F2', customer_id=cust.id, status='نشط')
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
            'fault_type': 'عطل',
            'priority': 'عادية',
            'client_report': 'اختبار',
            'billable': 'no',
        },
        headers={
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    assert data['dispatched'] is True
    assert 'wa.me' in (data.get('whatsapp_url') or '')
