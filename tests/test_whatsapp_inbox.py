"""اختبارات وارد واتساب — المرحلة 1."""
from flask import g

from models import Customer, Elevator, Organization, WhatsAppInbox, db
from tests.conftest import login_as
from whatsapp_support import (
    create_fault_from_inbox,
    find_customer_by_phone,
    intake_inbound,
    phone_key,
)


def test_phone_key_normalizes_saudi():
    assert phone_key('0555076078') == '555076078'
    assert phone_key('+966555076078') == '555076078'
    assert phone_key('966555076078') == '555076078'


def test_intake_matches_customer_and_creates_fault(client):
    from app import app

    login_as(client, 'admin')
    with app.app_context():
        org = Organization.query.filter_by(slug='default').first()
        g.organization = org
        g.organization_id = org.id
        cust = Customer(
            organization_id=org.id,
            code='C-WA01',
            name='عميل واتساب',
            phone='0555111222',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(
            organization_id=org.id,
            code='EL-WA01',
            customer_id=cust.id,
            status='نشط',
        )
        db.session.add(elev)
        db.session.commit()

        n = {'wa': 0, 'fa': 0}

        def _next(model, prefix, digits=5):
            if prefix.startswith('WA'):
                n['wa'] += 1
                return f'WA-{n["wa"]:05d}'
            n['fa'] += 1
            return f'FA-{n["fa"]:05d}'

        item = intake_inbound(
            from_phone='0555111222',
            body='المصعد واقف في الدور الثالث',
            next_code_fn=_next,
        )
        db.session.commit()
        assert item.customer_id == cust.id
        assert item.elevator_id == elev.id
        assert item.status == 'مربوط'
        assert find_customer_by_phone('0555111222').id == cust.id

        fault = create_fault_from_inbox(item, next_code_fn=_next)
        db.session.commit()
        assert fault.code == 'FA-00001'
        assert item.status == 'تم إنشاء عطل'
        assert item.fault_id == fault.id
        assert WhatsAppInbox.query.filter_by(id=item.id).first().fault_id == fault.id


def test_whatsapp_inbox_page_ok(client):
    login_as(client, 'admin')
    r = client.get('/support/whatsapp', base_url='https://app.liftcoreapp.com')
    assert r.status_code in (200, 302)
    if r.status_code == 200:
        assert 'وارد واتساب'.encode('utf-8') in r.data
        assert b'0555076078' in r.data
