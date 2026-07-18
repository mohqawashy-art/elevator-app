"""اختبارات وارد واتساب — المرحلة 1 و 2."""
from flask import g

from models import Customer, Elevator, Fault, Organization, WhatsAppInbox, db
from tests.conftest import login_as
from whatsapp_support import (
    JOURNEY_STAGES,
    build_customer_journey_message,
    create_fault_from_inbox,
    find_customer_by_phone,
    intake_inbound,
    notify_customer_stage,
    phone_key,
)


def test_phone_key_normalizes_saudi():
    assert phone_key('0555076078') == '555076078'
    assert phone_key('+966555076078') == '555076078'
    assert phone_key('966555076078') == '555076078'


def test_phone_preserves_international():
    from operations import whatsapp_digits
    from whatsapp_support import display_phone

    assert whatsapp_digits('+201012345678') == '201012345678'
    assert whatsapp_digits('00201012345678') == '201012345678'
    assert whatsapp_digits('+971501234567') == '971501234567'
    assert whatsapp_digits('0555076078') == '966555076078'
    assert whatsapp_digits('555076078') == '966555076078'
    assert whatsapp_digits('+966555076078') == '966555076078'
    # رقم دولي بدون + لكن بطول كافٍ — لا يُفرض 966
    assert whatsapp_digits('201012345678') == '201012345678'

    assert display_phone('+201012345678') == '+201012345678'
    assert display_phone('00201012345678') == '+201012345678'
    assert display_phone('0555076078') == '0555076078'
    assert phone_key('+201012345678') == '201012345678'
    assert phone_key('+201012345678') != phone_key('0555076078')


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


def test_journey_messages_include_fault_code(client):
    from app import app

    login_as(client, 'admin')
    with app.app_context():
        org = Organization.query.filter_by(slug='default').first()
        g.organization = org
        g.organization_id = org.id
        cust = Customer(
            organization_id=org.id,
            code='C-WA02',
            name='عميل رحلة',
            phone='0555222333',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(
            organization_id=org.id,
            code='EL-WA02',
            customer_id=cust.id,
            status='نشط',
        )
        db.session.add(elev)
        db.session.flush()
        fault = Fault(
            organization_id=org.id,
            code='FA-00999',
            elevator_id=elev.id,
            reporter_phone='0555222333',
            reporter_name='عميل رحلة',
            status='مفتوح',
            priority='عاجلة',
        )
        db.session.add(fault)
        db.session.commit()
        fault = Fault.query.filter_by(code='FA-00999').first()
        for stage in JOURNEY_STAGES:
            msg = build_customer_journey_message(fault, stage)
            assert 'FA-00999' in msg
            assert len(msg) > 20


def test_parts_needed_and_resolved_pdf_hint(client):
    from app import app

    login_as(client, 'admin')
    with app.app_context():
        org = Organization.query.filter_by(slug='default').first()
        g.organization = org
        g.organization_id = org.id
        cust = Customer(
            organization_id=org.id,
            code='C-WA05',
            name='عميل قطع',
            phone='0555666777',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(
            organization_id=org.id,
            code='EL-WA05',
            customer_id=cust.id,
            status='نشط',
        )
        db.session.add(elev)
        db.session.flush()
        fault = Fault(
            organization_id=org.id,
            code='FA-00555',
            elevator_id=elev.id,
            reporter_phone='0555666777',
            status='انتظار قطع',
        )
        db.session.add(fault)
        db.session.commit()
        fault = Fault.query.filter_by(code='FA-00555').first()
        msg = build_customer_journey_message(fault, 'parts_needed')
        assert 'قطع غيار' in msg
        assert 'FA-00555' in msg
        done = build_customer_journey_message(
            fault, 'resolved', report_url='https://example.com/faults/1/report?print=1',
        )
        assert 'تقرير الإصلاح' in done
        assert 'report?print=1' in done


def test_resolved_message_includes_summary_and_pending_queue(client):
    from app import app
    from whatsapp_support import pending_customer_sends, resolution_summary_for_fault

    login_as(client, 'admin')
    with app.app_context():
        org = Organization.query.filter_by(slug='default').first()
        g.organization = org
        g.organization_id = org.id
        cust = Customer(
            organization_id=org.id,
            code='C-WA04',
            name='عميل إغلاق',
            phone='0555444555',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(
            organization_id=org.id,
            code='EL-WA04',
            customer_id=cust.id,
            status='نشط',
        )
        db.session.add(elev)
        db.session.flush()
        fault = Fault(
            organization_id=org.id,
            code='FA-00777',
            elevator_id=elev.id,
            reporter_phone='0555444555',
            status='تم الاصلاح',
            resolution='تم استبدال كونتاكتور الباب',
            tech_notes='العطل في دائرة الباب',
        )
        db.session.add(fault)
        db.session.commit()
        fault = Fault.query.filter_by(code='FA-00777').first()
        assert 'كونتاكتور' in resolution_summary_for_fault(fault)
        msg = build_customer_journey_message(fault, 'resolved')
        assert 'ملخص الإصلاح' in msg
        assert 'كونتاكتور' in msg

        n = {'i': 0}

        def _next(model, prefix, digits=5):
            n['i'] += 1
            return f'{prefix}{n["i"]:05d}'

        result = notify_customer_stage(fault, 'resolved', next_code_fn=_next)
        db.session.commit()
        assert result['ok'] and result.get('pending_send')
        pending = pending_customer_sends()
        assert any(p['fault_code'] == 'FA-00777' for p in pending)


def test_notify_customer_stage_same_thread_code(client):
    from app import app

    login_as(client, 'admin')
    with app.app_context():
        org = Organization.query.filter_by(slug='default').first()
        g.organization = org
        g.organization_id = org.id
        cust = Customer(
            organization_id=org.id,
            code='C-WA03',
            name='عميل إشعار',
            phone='0555333444',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        elev = Elevator(
            organization_id=org.id,
            code='EL-WA03',
            customer_id=cust.id,
            status='نشط',
        )
        db.session.add(elev)
        db.session.flush()
        fault = Fault(
            organization_id=org.id,
            code='FA-00888',
            elevator_id=elev.id,
            reporter_phone='0555333444',
            status='مفتوح',
        )
        db.session.add(fault)
        db.session.commit()
        fault = Fault.query.filter_by(code='FA-00888').first()
        n = {'i': 0}

        def _next(model, prefix, digits=5):
            n['i'] += 1
            return f'{prefix}{n["i"]:05d}'

        first = notify_customer_stage(fault, 'received', next_code_fn=_next)
        db.session.commit()
        assert first['ok'] and first['url'].startswith('https://wa.me/')
        assert not first.get('skipped')
        thread_code = first['thread_code']
        assert thread_code.startswith('WA-')

        second = notify_customer_stage(fault, 'received', next_code_fn=_next)
        assert second['ok'] and second.get('skipped')
        assert second['thread_code'] == thread_code

        assigned = notify_customer_stage(fault, 'assigned', next_code_fn=_next)
        db.session.commit()
        assert assigned['ok'] and not assigned.get('skipped')
        assert assigned['thread_code'] == thread_code

        on_way = notify_customer_stage(fault, 'on_way', next_code_fn=_next)
        resolved = notify_customer_stage(fault, 'resolved', next_code_fn=_next)
        db.session.commit()
        assert on_way['thread_code'] == thread_code
        assert resolved['thread_code'] == thread_code

        threads = WhatsAppInbox.query.filter_by(fault_id=fault.id, direction='inbound').all()
        assert len(threads) == 1
        assert threads[0].code == thread_code
        import json
        journey = json.loads(threads[0].journey_json or '[]')
        assert [e['stage'] for e in journey] == ['received', 'assigned', 'on_way', 'resolved']
        outbound = WhatsAppInbox.query.filter_by(fault_id=fault.id, direction='outbound').count()
        assert outbound == 0
