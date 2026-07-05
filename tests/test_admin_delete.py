"""اختبارات حذف المسؤول — كلمة مرور إلزامية."""
from app import db
from models import Customer

from tests.conftest import login_as


def _seed_client():
    c = Customer(code='C-9999', name='للحذف', phone='+966512999999', status='نشط')
    db.session.add(c)
    db.session.commit()
    return c.id


def test_delete_without_password_rejected(client):
    login_as(client, 'admin')
    with client.application.app_context():
        cid = _seed_client()
    r = client.post(f'/clients/delete/{cid}', data={}, follow_redirects=False)
    assert r.status_code in (302, 403)
    with client.application.app_context():
        assert db.session.get(Customer, cid) is not None


def test_delete_wrong_password_rejected(client):
    login_as(client, 'admin')
    with client.application.app_context():
        cid = _seed_client()
    r = client.post(
        f'/clients/delete/{cid}',
        data={'admin_password': 'WrongPass999!'},
        headers={'X-LC-Admin-Delete': '1'},
        follow_redirects=False,
    )
    assert r.status_code in (302, 403)
    with client.application.app_context():
        assert db.session.get(Customer, cid) is not None


def test_delete_correct_password_works(client):
    login_as(client, 'admin')
    with client.application.app_context():
        cid = _seed_client()
    r = client.post(
        f'/clients/delete/{cid}',
        data={'admin_password': 'TestPass123!'},
        headers={'X-LC-Admin-Delete': '1'},
        follow_redirects=False,
    )
    assert r.status_code in (302, 200)
    with client.application.app_context():
        assert db.session.get(Customer, cid) is None
