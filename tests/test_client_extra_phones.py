"""اختبار أرقام العميل الإضافية."""
from __future__ import annotations

from app import (
    parse_customer_extra_phones,
    parse_extra_phones_from_request,
    serialize_customer_extra_phones,
)
from models import Customer
from tests.conftest import login_as


def test_parse_extra_phones_roundtrip():
    raw = serialize_customer_extra_phones([
        {'label': 'محاسب', 'number': '0555123456'},
        {'label': '', 'number': '+966555998877'},
    ])
    items = parse_customer_extra_phones(raw)
    assert len(items) == 2
    assert items[0]['label'] == 'محاسب'
    assert items[0]['number'].startswith('+966')
    assert items[1]['number'] == '+966555998877'


def test_client_add_saves_extra_phones(client):
    login_as(client, 'admin')
    r = client.post('/clients/add', data={
        'name': 'عميل أرقام متعددة',
        'phone': '+966512345678',
        'phone2': '+966598765432',
        'extra_phones': '[{"label":"حارس","number":"0555111222"},{"label":"طوارئ","number":"0555333444"}]',
        'entity_type': 'فرد',
        'status': 'نشط',
        'city': 'مكة المكرمة',
    }, follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        c = Customer.query.filter_by(name='عميل أرقام متعددة').first()
        assert c is not None
        extras = parse_customer_extra_phones(c.extra_phones)
        assert len(extras) == 2
        assert extras[0]['label'] == 'حارس'
        assert extras[1]['number'].endswith('555333444') or '555333444' in extras[1]['number']


def test_responsible_whatsapp_can_be_reused(client):
    login_as(client, 'admin')
    first = client.post('/clients/add', data={
        'name': 'عميل مسؤول أول',
        'phone': '+966511100001',
        'phone2': '+966522200002',
        'entity_type': 'فرد',
        'status': 'نشط',
    }, follow_redirects=True)
    assert first.status_code == 200
    second = client.post('/clients/add', data={
        'name': 'عميل مسؤول ثان',
        'phone': '+966511100003',
        'phone2': '0522200002',
        'entity_type': 'شركة',
        'status': 'نشط',
    }, follow_redirects=True)
    assert second.status_code == 200
    with client.application.app_context():
        rows = Customer.query.filter(Customer.name.in_(['عميل مسؤول أول', 'عميل مسؤول ثان'])).all()
        assert len(rows) == 2
        assert {r.phone2 for r in rows} == {'+966522200002'}

    blocked = client.post('/clients/add', data={
        'name': 'عميل جوال مكرر',
        'phone': '+966511100001',
        'phone2': '+966533300004',
        'entity_type': 'فرد',
        'status': 'نشط',
    }, follow_redirects=True)
    assert blocked.status_code == 200
    with client.application.app_context():
        assert Customer.query.filter_by(name='عميل جوال مكرر').first() is None


def test_parse_extra_phones_rejects_bad_number():
    class Form(dict):
        def getlist(self, key):
            return []

    form = Form({'extra_phones': '[{"label":"x","number":"12"}]'})
    items, err = parse_extra_phones_from_request(form)
    assert items is None
    assert err
