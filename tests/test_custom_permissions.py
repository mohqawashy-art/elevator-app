"""اختبارات الدور «مخصص»."""
from tests.conftest import login_as


def test_custom_role_user_gets_finance_only(client):
    from app import db, hash_password
    from models import Organization, User
    from liftcore_permissions import dump_permissions_extra

    with client.application.app_context():
        org_id = Organization.query.filter_by(slug='default').first().id
        u = User(
            username='acct_user',
            password_hash=hash_password('TestPass123!'),
            role='custom',
            is_active=True,
            organization_id=org_id,
            permissions_extra=dump_permissions_extra([
                'revenues.read', 'expenses.read', 'invoices.read',
                'revenues.create', 'revenues.edit',
                'expenses.create', 'expenses.edit',
                'invoices.create', 'invoices.edit',
            ]),
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id

    with client.session_transaction() as sess:
        sess['user_id'] = uid
        sess['session_version'] = 0
        sess['lang'] = 'ar'

    assert client.get('/invoices', follow_redirects=False).status_code == 200
    assert client.get('/clients', follow_redirects=False).status_code == 403


def test_custom_role_can_write_when_granted(client):
    from app import db, hash_password
    from models import Organization, User
    from liftcore_permissions import dump_permissions_extra

    with client.application.app_context():
        org_id = Organization.query.filter_by(slug='default').first().id
        u = User(
            username='sales_user',
            password_hash=hash_password('TestPass123!'),
            role='custom',
            is_active=True,
            organization_id=org_id,
            permissions_extra=dump_permissions_extra(['clients.read', 'clients.create']),
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id

    with client.session_transaction() as sess:
        sess['user_id'] = uid
        sess['session_version'] = 0
        sess['lang'] = 'ar'

    r = client.post(
        '/clients/add',
        data={'name': 'عميل مخصص', 'phone': '512345678', 'city': 'مكة'},
        follow_redirects=False,
    )
    assert r.status_code in (200, 302)
    assert r.status_code != 403


def test_custom_role_add_only_cannot_edit(client):
    from app import db, hash_password
    from models import Customer, Organization, User
    from liftcore_permissions import dump_permissions_extra

    with client.application.app_context():
        org_id = Organization.query.filter_by(slug='default').first().id
        u = User(
            username='add_only_user',
            password_hash=hash_password('TestPass123!'),
            role='custom',
            is_active=True,
            organization_id=org_id,
            permissions_extra=dump_permissions_extra(['clients.read', 'clients.create']),
        )
        db.session.add(u)
        db.session.flush()
        customer = Customer(
            organization_id=org_id,
            code='C-T001',
            name='عميل اختبار',
            phone='512300000',
            city='مكة',
            status='نشط',
        )
        db.session.add(customer)
        db.session.commit()
        uid = u.id
        cid = customer.id

    with client.session_transaction() as sess:
        sess['user_id'] = uid
        sess['session_version'] = 0
        sess['lang'] = 'ar'

    r = client.post(
        f'/clients/edit/{cid}',
        data={'name': 'عميل معدل', 'phone': '512300001', 'city': 'مكة'},
        follow_redirects=False,
    )
    assert r.status_code == 403


def test_manager_unchanged_without_custom_role(client):
    login_as(client, 'manager')
    r = client.get('/invoices', follow_redirects=False)
    assert r.status_code == 200
    r2 = client.post(
        '/settings/profile',
        data={'full_name': 'مدير'},
        follow_redirects=False,
    )
    assert r2.status_code in (200, 302)
    assert r2.status_code != 403


def test_admin_can_add_custom_user(client):
    login_as(client, 'admin')
    r = client.post(
        '/settings/users/add',
        data={
            'username': 'user_custom1',
            'password': 'TestPass123!',
            'role': 'custom',
            'perm_grant': ['faults.read', 'faults.create', 'faults.edit'],
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    from app import db
    from models import User
    from liftcore_permissions import parse_permissions_extra

    with client.application.app_context():
        u = User.query.filter_by(username='user_custom1').first()
        assert u is not None
        assert u.role == 'custom'
        perms = parse_permissions_extra(u.permissions_extra)
        assert 'faults.read' in perms['grants']
        assert 'faults.create' in perms['grants']
        assert 'faults.edit' in perms['grants']


def test_legacy_permissions_are_upgraded(client):
    from liftcore_permissions import parse_permissions_extra

    perms = parse_permissions_extra('{"grants":["clients.read","clients.write"],"denies":[]}')
    assert 'clients.read' in perms['grants']
    assert 'clients.create' in perms['grants']
    assert 'clients.edit' in perms['grants']
    assert 'contracts.create' in perms['grants']


def test_ensure_permissions_schema_adds_users_column(client):
    from app import db
    from liftcore_permissions import ensure_permissions_schema
    from sqlalchemy import inspect

    with client.application.app_context():
        ensure_permissions_schema(db.session, db.engine)
        users_cols = {c['name'] for c in inspect(db.engine).get_columns('users')}
        assert 'permissions_extra' in users_cols
