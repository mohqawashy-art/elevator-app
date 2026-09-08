"""تقرير العطل يحفظ قطع الغيار مع صنف المخزن."""
from models import Customer, Elevator, Fault, InventoryItem, Technician, db
from tests.conftest import login_as


def test_fault_report_keeps_inventory_item_id_on_parts(client):
    login_as(client, role='admin')
    with client.application.app_context():
        from tests.conftest import ensure_test_organization
        oid = ensure_test_organization()
        tech = Technician(
            organization_id=oid,
            code='T-INVFR',
            name='فني تقرير مخزن',
            phone='0500000001',
            team='صيانة',
            status='متاح',
        )
        cust = Customer(organization_id=oid, code='C-INVFR', name='عميل تقرير', status='نشط')
        item = InventoryItem(
            organization_id=oid,
            code='BR-9',
            name='براش محرك',
            unit='قطعة',
            buy_price=20,
            sell_price=55,
            current_qty=10,
        )
        db.session.add_all([tech, cust, item])
        db.session.flush()
        elev = Elevator(organization_id=oid, code='E-INVFR', customer_id=cust.id, status='نشط')
        db.session.add(elev)
        db.session.flush()
        fault = Fault(
            organization_id=oid,
            code='F-INVFR',
            elevator_id=elev.id,
            technician_id=tech.id,
            fault_type='عطل محرك',
            status='قيد المعالجة',
            client_report='صوت',
        )
        db.session.add(fault)
        db.session.commit()
        fault_id, item_id = fault.id, item.id

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    resp = client.post(
        f'/api/faults/{fault_id}/report',
        json={
            'csrf_token': 'test-csrf',
            'meta': {'diagnosis': 'براش تالف', 'action_taken': 'استبدال', 'visit_outcome': 'solved'},
            'parts': [{'item_id': item_id, 'name': 'براش محرك', 'qty': 2, 'unit_price': 55}],
            'signatures': {},
            'photos': [],
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json().get('ok') is True

    with client.application.app_context():
        saved = Fault.query.get(fault_id)
        import json
        data = json.loads(saved.report_json or '{}')
        parts = data.get('parts') or []
        assert parts
        assert parts[0].get('item_id') == item_id
        assert parts[0].get('qty') == 2
        assert float(parts[0].get('unit_price') or 0) == 55
