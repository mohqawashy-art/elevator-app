"""إثبات حركات العطل: وصول، طلب قطع، استلام المكتب، إغلاق."""
from models import Customer, Elevator, Fault, FaultEvent, Technician, db
from tests.conftest import login_as


def _fault(app):
    with app.app_context():
        from tests.conftest import ensure_test_organization
        oid = ensure_test_organization()
        tech = Technician(
            organization_id=oid,
            code='T-EV',
            name='محمود الفني',
            phone='0500000099',
            team='أعطال',
            status='متاح',
        )
        cust = Customer(organization_id=oid, code='C-EV', name='عميل حركة', status='نشط')
        db.session.add_all([tech, cust])
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-EV', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()
        fault = Fault(
            organization_id=oid,
            code='FA-EV',
            elevator_id=elev.id,
            technician_id=tech.id,
            fault_type='عطل كهربائي',
            status='مفتوح',
            client_report='المصعد واقف',
        )
        db.session.add(fault)
        db.session.commit()
        return fault.id, tech.id


def test_arrival_parts_receive_and_close(client):
    from app import app
    from operations import (
        receive_fault_parts_request,
        request_fault_parts,
        stamp_field_fault_arrival,
    )

    fault_id, tech_id = _fault(app)
    with app.app_context():
        stamp_field_fault_arrival(fault_id, tech_id=tech_id)
        stamp_field_fault_arrival(fault_id, tech_id=tech_id)
        request_fault_parts(fault_id, description='كونتاكتور + فيوز', sell_price=0)
        arrived = FaultEvent.query.filter_by(fault_id=fault_id, event_type='arrived').all()
        requested = FaultEvent.query.filter_by(fault_id=fault_id, event_type='parts_requested').all()
        assert len(arrived) == 1
        assert arrived[0].actor_name == 'محمود الفني'
        assert len(requested) == 1
        assert 'كونتاكتور' in (requested[0].detail or '')

    login_as(client, role='admin')
    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'
    resp = client.post(f'/api/faults/{fault_id}/parts-received', json={'csrf_token': 'test-csrf'})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body['ok'] is True
    received = [ev for ev in body['events'] if ev['type'] == 'parts_received']
    assert received and received[0]['actor'] == 'admin'
    assert 'كونتاكتور' in received[0]['detail']
    types = [ev['type'] for ev in body['events']]
    assert types.index('parts_requested') < types.index('parts_received')
    assert body['parts_next'] == 'supply'

    again = client.post(f'/api/faults/{fault_id}/parts-received', json={'csrf_token': 'test-csrf'})
    assert again.status_code == 400

    with app.app_context():
        from operations import complete_field_fault
        complete_field_fault(
            fault_id,
            tech_notes='تم التغيير',
            resolution='استبدال الكونتاكتور',
            status='تم الاصلاح',
        )
        closed = FaultEvent.query.filter_by(fault_id=fault_id, event_type='closed').all()
        assert len(closed) == 1
        assert closed[0].actor_role == 'technician'
        assert 'استبدال' in (closed[0].detail or '')


def test_priced_parts_go_through_customer_approval_then_supply(client):
    from app import app
    from models import PartsBilling
    from operations import request_fault_parts, stamp_field_fault_arrival

    fault_id, tech_id = _fault(app)
    with app.app_context():
        stamp_field_fault_arrival(fault_id, tech_id=tech_id)
        request_fault_parts(fault_id, description='لوحة تحكم', sell_price=250)

    login_as(client, role='admin')
    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    early = client.post(
        f'/api/faults/{fault_id}/parts-action',
        json={'action': 'supply', 'csrf_token': 'test-csrf'},
    )
    assert early.status_code == 400

    received = client.post(
        f'/api/faults/{fault_id}/parts-action',
        json={'action': 'receive', 'csrf_token': 'test-csrf'},
    )
    assert received.status_code == 200, received.get_data(as_text=True)
    assert received.get_json()['parts_next'] == 'approve'

    approved = client.post(
        f'/api/faults/{fault_id}/parts-action',
        json={'action': 'approve', 'csrf_token': 'test-csrf'},
    )
    body = approved.get_json()
    assert approved.status_code == 200, approved.get_data(as_text=True)
    assert body['parts_next'] == 'supply'
    assert any(ev['type'] == 'customer_approved' for ev in body['events'])

    supplied = client.post(
        f'/api/faults/{fault_id}/parts-action',
        json={'action': 'supply', 'csrf_token': 'test-csrf'},
    )
    done = supplied.get_json()
    assert supplied.status_code == 200, supplied.get_data(as_text=True)
    assert done['parts_next'] == ''
    assert done['status'] == 'قيد المعالجة'
    assert any(ev['title'] == 'تم توفير قطع الغيار' for ev in done['events'])
    types = [ev['type'] for ev in done['events']]
    assert types.index('parts_received') < types.index('customer_approved') < types.index('parts_supplied')

    with app.app_context():
        pb = PartsBilling.query.filter_by(fault_id=fault_id).one()
        assert pb.status == 'غير محصل'
