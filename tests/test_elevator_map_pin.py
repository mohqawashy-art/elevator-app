"""موقع المصعد على الخريطة يتبع GPS العقد الدقيق وليس مركز المدينة."""
from datetime import date, timedelta

from app import db, elevator_to_js_dict
from models import Contract, ContractElevator, Customer, Elevator

from tests.conftest import ensure_test_organization, login_as


def test_elevator_js_prefers_contract_gps(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        from flask import g
        g.organization_id = oid
        cust = Customer(
            organization_id=oid,
            code='C-ELMAP1',
            name='عميل مصعد',
            status='نشط',
            city='مكة',
            lat='21.4225',
            lng='39.8262',
        )
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(
            organization_id=oid,
            code='EL-MAP1',
            customer_id=cust.id,
            city='مكة',
            status='نشط',
            floors=5,
        )
        db.session.add(elev)
        db.session.flush()
        c = Contract(
            organization_id=oid,
            code='CN-ELMAP1',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            status='نشط',
            value=0,
            tax_pct=15,
            tax_amount=0,
            total=0,
            lat='21.389',
            lng='39.857',
        )
        db.session.add(c)
        db.session.flush()
        db.session.add(ContractElevator(
            organization_id=oid,
            contract_id=c.id,
            elevator_id=elev.id,
        ))
        db.session.commit()
        elev = db.session.get(Elevator, elev.id)
        data = elevator_to_js_dict(elev)
        assert data['lat'] == '21.389'
        assert data['lng'] == '39.857'


def test_elevator_edit_saves_pin_to_customer(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer(
            organization_id=oid,
            code='C-ELMAP2',
            name='عميل دبوس',
            status='نشط',
            lat='21.4225',
            lng='39.8262',
        )
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(
            organization_id=oid,
            code='EL-MAP2',
            customer_id=cust.id,
            status='نشط',
            floors=4,
        )
        db.session.add(elev)
        db.session.commit()
        eid, cust_id = elev.id, cust.id

    r = client.post(
        f'/elevators/edit/{eid}',
        data={
            'customer_id': str(cust_id),
            'floors': '4',
            'city': 'مكة',
            'district': 'العوالي',
            'lat': '21.4011',
            'lng': '39.8111',
            'maps_url': 'https://www.google.com/maps?q=21.4011,39.8111',
        },
        follow_redirects=False,
    )
    assert r.status_code in (200, 302)
    with client.application.app_context():
        saved = db.session.get(Customer, cust_id)
        assert saved.lat == '21.4011'
        assert saved.lng == '39.8111'
