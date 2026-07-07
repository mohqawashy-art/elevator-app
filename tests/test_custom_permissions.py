"""اختبارات الصلاحيات الاختيارية."""
from tests.conftest import login_as


def _enable_custom_permissions(client):
    from app import db
    from models import Settings

    with client.application.app_context():
        s = Settings.query.first()
        s.custom_permissions_enabled = True
        db.session.commit()


def test_custom_permissions_disabled_uses_roles(client):
    login_as(client, 'viewer')
    r = client.post('/clients/add', data={'name': 'X', 'phone': '512345678'}, follow_redirects=False)
    assert r.status_code in (403, 302)


def test_viewer_grant_finance_read_blocks_finance_path(client):
    _enable_custom_permissions(client)
    from app import db
    from models import User
    from liftcore_permissions import dump_permissions_extra

    with client.application.app_context():
        u = User.query.filter_by(username='test_viewer').first()
        u.permissions_extra = dump_permissions_extra([], ['finance.read'])
        db.session.commit()

    login_as(client, 'viewer')
    r = client.get('/invoices', follow_redirects=False)
    assert r.status_code == 403


def test_viewer_grant_clients_write_can_post(client):
    _enable_custom_permissions(client)
    from app import db
    from models import User
    from liftcore_permissions import dump_permissions_extra

    with client.application.app_context():
        u = User.query.filter_by(username='test_viewer').first()
        u.permissions_extra = dump_permissions_extra(['clients.write'], [])
        db.session.commit()

    login_as(client, 'viewer')
    r = client.post(
        '/clients/add',
        data={'name': 'عميل صلاحيات', 'phone': '512345678', 'city': 'مكة'},
        follow_redirects=False,
    )
    assert r.status_code in (200, 302)
    assert r.status_code != 403


def test_manager_deny_operations_read(client):
    _enable_custom_permissions(client)
    from app import db
    from models import User
    from liftcore_permissions import dump_permissions_extra

    with client.application.app_context():
        u = User.query.filter_by(username='test_manager').first()
        u.permissions_extra = dump_permissions_extra([], ['operations.read'])
        db.session.commit()

    login_as(client, 'manager')
    r = client.get('/maintenance-visits', follow_redirects=False)
    assert r.status_code == 403


def test_settings_toggle_custom_permissions(client):
    login_as(client, 'admin')
    r = client.post(
        '/settings/custom-permissions',
        data={'custom_permissions_enabled': '1'},
        follow_redirects=False,
    )
    assert r.status_code == 302
    from app import db
    from models import Settings

    with client.application.app_context():
        assert Settings.query.first().custom_permissions_enabled is True


def test_has_perm_template_global(client):
    login_as(client, 'admin')
    r = client.get('/dashboard')
    assert r.status_code == 200
    assert b'/clients' in r.data
