"""حذف المرفقات — مدير النظام + كلمة مرور فقط."""
import os
from datetime import date, timedelta

from app import db
from models import Contract, Customer, Expense, Revenue

from tests.conftest import ensure_test_organization, login_as


def _touch_static(app, relative: str, content: bytes = b'x') -> str:
    full = os.path.join(app.root_path, 'static', relative.replace('/', os.sep))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'wb') as fh:
        fh.write(content)
    return relative


def test_contract_remove_file_requires_admin_password(client):
    login_as(client, 'admin')
    app = client.application
    with app.app_context():
        oid = ensure_test_organization()
        cust = Customer(
            organization_id=oid, code='C-ATT1', name='مرفق', phone='+966500000001', status='نشط'
        )
        db.session.add(cust)
        db.session.flush()
        path = _touch_static(app, 'uploads/contracts/9001/test.pdf', b'%PDF')
        c = Contract(
            organization_id=oid,
            code='CN-ATT01',
            customer_id=cust.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            value=100,
            total=115,
            file_path=path,
            status='نشط',
        )
        db.session.add(c)
        db.session.commit()
        cid = c.id

    r = client.post(f'/contracts/{cid}/remove-file', headers={'Accept': 'application/json'})
    assert r.status_code == 403

    r = client.post(
        f'/contracts/{cid}/remove-file',
        json={'admin_password': 'WrongPass'},
        headers={'X-LC-Admin-Delete': '1', 'Accept': 'application/json'},
    )
    assert r.status_code == 403

    r = client.post(
        f'/contracts/{cid}/remove-file',
        json={'admin_password': 'TestPass123!'},
        headers={'X-LC-Admin-Delete': '1', 'Accept': 'application/json'},
    )
    assert r.status_code == 200
    assert r.get_json().get('ok') is True
    with app.app_context():
        assert db.session.get(Contract, cid).file_path is None


def test_contract_remove_file_manager_forbidden(client):
    login_as(client, 'manager')
    app = client.application
    with app.app_context():
        oid = ensure_test_organization()
        cust = Customer(
            organization_id=oid, code='C-ATT2', name='مرفق2', phone='+966500000002', status='نشط'
        )
        db.session.add(cust)
        db.session.flush()
        path = _touch_static(app, 'uploads/contracts/9002/test.pdf', b'%PDF')
        c = Contract(
            organization_id=oid,
            code='CN-ATT02',
            customer_id=cust.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            value=100,
            total=115,
            file_path=path,
            status='نشط',
        )
        db.session.add(c)
        db.session.commit()
        cid = c.id

    r = client.post(
        f'/contracts/{cid}/remove-file',
        json={'admin_password': 'TestPass123!'},
        headers={'X-LC-Admin-Delete': '1', 'Accept': 'application/json'},
    )
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(Contract, cid).file_path


def test_revenue_remove_proof_admin_ok(client):
    login_as(client, 'admin')
    app = client.application
    with app.app_context():
        oid = ensure_test_organization()
        cust = Customer(
            organization_id=oid, code='C-ATT3', name='إيراد', phone='+966500000003', status='نشط'
        )
        db.session.add(cust)
        db.session.flush()
        path = _touch_static(app, 'uploads/financial_proofs/revenues/9003/p.pdf', b'%PDF')
        rev = Revenue(
            organization_id=oid,
            code='REV-ATT1',
            customer_id=cust.id,
            revenue_date=date.today(),
            amount=100,
            tax_amount=15,
            total=115,
            status='محصّل',
            proof_path=path,
        )
        db.session.add(rev)
        db.session.commit()
        rid = rev.id

    r = client.post(
        f'/revenues/{rid}/remove-proof',
        json={'admin_password': 'TestPass123!'},
        headers={'X-LC-Admin-Delete': '1', 'Accept': 'application/json'},
    )
    assert r.status_code == 200
    with app.app_context():
        assert db.session.get(Revenue, rid).proof_path is None


def test_revenue_remove_proof_at_index(client):
    login_as(client, 'admin')
    app = client.application
    with app.app_context():
        oid = ensure_test_organization()
        cust = Customer(
            organization_id=oid, code='C-ATT6', name='إيراد2', phone='+966500000006', status='نشط'
        )
        db.session.add(cust)
        db.session.flush()
        p1 = _touch_static(app, 'uploads/financial_proofs/revenues/9006/a.pdf', b'%PDF1')
        p2 = _touch_static(app, 'uploads/financial_proofs/revenues/9006/b.pdf', b'%PDF2')
        from attachment_paths import serialize_attachment_paths

        rev = Revenue(
            organization_id=oid,
            code='REV-ATT2',
            customer_id=cust.id,
            revenue_date=date.today(),
            amount=100,
            tax_amount=15,
            total=115,
            status='محصّل',
            proof_path=serialize_attachment_paths([p1, p2]),
        )
        db.session.add(rev)
        db.session.commit()
        rid = rev.id

    r = client.post(
        f'/revenues/{rid}/remove-proof',
        json={'admin_password': 'TestPass123!', 'index': 0},
        headers={'X-LC-Admin-Delete': '1', 'Accept': 'application/json'},
    )
    assert r.status_code == 200
    with app.app_context():
        from attachment_paths import parse_attachment_paths

        paths = parse_attachment_paths(db.session.get(Revenue, rid).proof_path)
        assert paths == [p2]


def test_expense_remove_proof_admin_ok(client):
    login_as(client, 'admin')
    app = client.application
    with app.app_context():
        oid = ensure_test_organization()
        path = _touch_static(app, 'uploads/financial_proofs/expenses/9004/p.pdf', b'%PDF')
        exp = Expense(
            organization_id=oid,
            code='EXP-ATT1',
            expense_date=date.today(),
            expense_type='محروقات',
            amount=50,
            proof_path=path,
        )
        db.session.add(exp)
        db.session.commit()
        eid = exp.id

    r = client.post(
        f'/expenses/{eid}/remove-proof',
        json={'admin_password': 'TestPass123!'},
        headers={'X-LC-Admin-Delete': '1', 'Accept': 'application/json'},
    )
    assert r.status_code == 200
    with app.app_context():
        assert db.session.get(Expense, eid).proof_path is None


def test_client_remove_building_photo_admin_ok(client):
    login_as(client, 'admin')
    app = client.application
    with app.app_context():
        oid = ensure_test_organization()
        path = _touch_static(app, 'uploads/clients/9005/building.jpg', b'\xff\xd8')
        cust = Customer(
            organization_id=oid,
            code='C-ATT5',
            name='مبنى',
            phone='+966500000005',
            status='نشط',
            building_photo_path=path,
        )
        db.session.add(cust)
        db.session.commit()
        cid = cust.id

    r = client.post(
        f'/clients/{cid}/remove-building-photo',
        json={'admin_password': 'TestPass123!'},
        headers={'X-LC-Admin-Delete': '1', 'Accept': 'application/json'},
    )
    assert r.status_code == 200
    with app.app_context():
        assert db.session.get(Customer, cid).building_photo_path is None
