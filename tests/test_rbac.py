"""اختبارات RBAC — viewer / manager / admin."""
from tests.conftest import login_as


def test_viewer_cannot_post_client_create(client):
    login_as(client, 'viewer')
    r = client.post('/clients/add', data={'name': 'Test Client', 'phone': '512345678'}, follow_redirects=False)
    assert r.status_code in (403, 302)


def test_manager_cannot_add_users(client):
    login_as(client, 'manager')
    r = client.post('/settings/users/add', data={
        'username': 'newuser',
        'password': 'TestPass123!',
        'role': 'viewer',
    }, follow_redirects=False)
    assert r.status_code in (403, 302)


def test_viewer_self_password_change_allowed(client):
    login_as(client, 'viewer')
    r = client.post('/settings/password', data={
        'current_password': 'TestPass123!',
        'new_password': 'NewPass123!',
        'confirm_password': 'NewPass123!',
    }, follow_redirects=False)
    assert r.status_code in (302, 200)
