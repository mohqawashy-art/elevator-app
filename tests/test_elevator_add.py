"""تسجيل مصعد من المكتب — JSON بدون إعادة تحميل + redirect التقليدي."""
from __future__ import annotations

from models import Customer, Elevator, db
from tests.conftest import ensure_test_organization, login_as


def _seed_customer():
    oid = ensure_test_organization()
    cust = Customer(organization_id=oid, code='C-EL1', name='عميل مصعد', status='نشط')
    db.session.add(cust)
    db.session.commit()
    return cust.id


def test_elevator_add_redirects_without_json(client):
    login_as(client, 'admin')
    with client.application.app_context():
        customer_id = _seed_customer()

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    r = client.post(
        '/elevators/add',
        data={
            'csrf_token': 'test-csrf',
            'customer_id': str(customer_id),
            'building_name': 'برج الاختبار',
            'city': 'مكة',
            'elev_type': 'مصعد ركاب',
            'floors': '5',
            'status': 'نشط',
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert '/elevators' in (r.headers.get('Location') or '')
    with client.application.app_context():
        elev = Elevator.query.filter_by(customer_id=customer_id).first()
        assert elev is not None
        assert elev.code.startswith('EL-')
        assert elev.building_name == 'برج الاختبار'


def test_elevator_add_json_returns_elevator(client):
    login_as(client, 'admin')
    with client.application.app_context():
        customer_id = _seed_customer()

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    r = client.post(
        '/elevators/add',
        data={
            'csrf_token': 'test-csrf',
            'customer_id': str(customer_id),
            'building_name': 'عمارة سريعة',
            'city': 'جدة',
            'elev_type': 'مصعد ركاب',
            'floors': '8',
            'capacity_kg': '630',
            'status': 'نشط',
        },
        headers={
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    elev = data['elevator']
    assert elev['id']
    assert elev['code'].startswith('EL-')
    assert elev['customer_id'] == customer_id
    assert elev['building'] == 'عمارة سريعة'
    assert elev['city'] == 'جدة'
    assert data['next_code'].startswith('EL-')
    assert data['next_code'] != elev['code']


def test_elevator_add_json_validation_error(client):
    login_as(client, 'admin')
    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test-csrf'

    r = client.post(
        '/elevators/add',
        data={
            'csrf_token': 'test-csrf',
            'building_name': 'بدون عميل',
            'floors': '3',
        },
        headers={
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
        },
    )
    assert r.status_code == 400
    data = r.get_json()
    assert data['ok'] is False
    assert data.get('error')
