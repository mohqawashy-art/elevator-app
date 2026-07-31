"""تغيير عميل العقد يتطلب موافقة مدير النظام + كلمة المرور."""
from datetime import date, timedelta

from app import db
from models import Contract, Customer

from tests.conftest import ensure_test_organization, login_as


def _seed_contract_with_two_clients():
    oid = ensure_test_organization()
    a = Customer(organization_id=oid, code='C-9001', name='عميل أصلي', status='نشط')
    b = Customer(organization_id=oid, code='C-9002', name='عميل بديل', status='نشط')
    db.session.add_all([a, b])
    db.session.flush()
    c = Contract(
        organization_id=oid,
        code='CN-90001',
        customer_id=a.id,
        contract_type='عقد صيانة',
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        duration_months=12,
        value=1000,
        tax_pct=15,
        tax_amount=150,
        total=1150,
        status='نشط',
    )
    db.session.add(c)
    db.session.commit()
    return c.id, a.id, b.id


def _edit_payload(customer_id, admin_password=None):
    data = {
        'customer_id': str(customer_id),
        'contract_type': 'عقد صيانة',
        'start_date': date.today().isoformat(),
        'end_date': (date.today() + timedelta(days=365)).isoformat(),
        'maint_frequency': 'شهري',
        'visits_per_month': '1',
        'value': '1000',
        'tax_pct': '15',
        'total': '1150',
        'payment_terms': 'دفعة واحدة',
        'status': 'نشط',
    }
    if admin_password is not None:
        data['admin_password'] = admin_password
    return data


def test_change_contract_client_without_password_rejected(client):
    login_as(client, 'admin')
    with client.application.app_context():
        cid, a_id, b_id = _seed_contract_with_two_clients()
    r = client.post(
        f'/contracts/edit/{cid}',
        data=_edit_payload(b_id),
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        follow_redirects=False,
    )
    assert r.status_code == 403
    with client.application.app_context():
        assert db.session.get(Contract, cid).customer_id == a_id


def test_change_contract_client_wrong_password_rejected(client):
    login_as(client, 'admin')
    with client.application.app_context():
        cid, a_id, b_id = _seed_contract_with_two_clients()
    r = client.post(
        f'/contracts/edit/{cid}',
        data=_edit_payload(b_id, 'WrongPass999!'),
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        follow_redirects=False,
    )
    assert r.status_code == 403
    with client.application.app_context():
        assert db.session.get(Contract, cid).customer_id == a_id


def test_change_contract_client_with_admin_password_works(client):
    login_as(client, 'admin')
    with client.application.app_context():
        cid, _a_id, b_id = _seed_contract_with_two_clients()
    r = client.post(
        f'/contracts/edit/{cid}',
        data=_edit_payload(b_id, 'TestPass123!'),
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        follow_redirects=False,
    )
    assert r.status_code in (200, 302)
    with client.application.app_context():
        assert db.session.get(Contract, cid).customer_id == b_id


def test_change_contract_client_manager_forbidden(client):
    login_as(client, 'manager')
    with client.application.app_context():
        cid, a_id, b_id = _seed_contract_with_two_clients()
    r = client.post(
        f'/contracts/edit/{cid}',
        data=_edit_payload(b_id, 'TestPass123!'),
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        follow_redirects=False,
    )
    assert r.status_code == 403
    with client.application.app_context():
        assert db.session.get(Contract, cid).customer_id == a_id


def test_edit_contract_same_client_no_password_needed(client):
    login_as(client, 'manager')
    with client.application.app_context():
        cid, a_id, _b_id = _seed_contract_with_two_clients()
    r = client.post(
        f'/contracts/edit/{cid}',
        data=_edit_payload(a_id),
        follow_redirects=False,
    )
    assert r.status_code in (200, 302)
    with client.application.app_context():
        c = db.session.get(Contract, cid)
        assert c.customer_id == a_id
        assert c.value == 1000
