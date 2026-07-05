"""اختبارات تدفقات أساسية — login، عميل، صفحات، health."""
from models import Customer

from tests.conftest import login_as


def test_login_page_ok(client):
    r = client.get('/login')
    assert r.status_code == 200


def test_login_success_redirects(client):
    r = client.post('/login', data={
        'username': 'test_admin',
        'password': 'TestPass123!',
    }, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert 'welcome' in (r.location or '') or 'dashboard' in (r.location or '')


def test_login_wrong_password(client):
    r = client.post('/login', data={
        'username': 'test_admin',
        'password': 'WrongPass999!',
    })
    assert r.status_code == 200
    assert 'غير صحيحة' in r.get_data(as_text=True)


def test_dashboard_requires_auth(client):
    r = client.get('/dashboard', follow_redirects=False)
    assert r.status_code in (302, 303)
    assert 'login' in (r.location or '')


def test_dashboard_ok_for_admin(client):
    login_as(client, 'admin')
    r = client.get('/dashboard')
    assert r.status_code == 200


def test_api_health(client):
    r = client.get('/api/health')
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('database') is True
    assert 'version' in data


def test_client_add_as_admin(client):
    login_as(client, 'admin')
    r = client.post('/clients/add', data={
        'name': 'عميل اختبار',
        'phone': '512345678',
        'city': 'مكة',
        'status': 'نشط',
    }, follow_redirects=False)
    assert r.status_code in (302, 303)
    with client.application.app_context():
        c = Customer.query.filter_by(name='عميل اختبار').first()
        assert c is not None
        assert c.phone


def test_invoices_page_ok(client):
    login_as(client, 'admin')
    r = client.get('/invoices')
    assert r.status_code == 200


def test_maintenance_visits_page_ok(client):
    login_as(client, 'admin')
    r = client.get('/maintenance-visits')
    assert r.status_code == 200


def test_parts_report_page_ok(client):
    login_as(client, 'admin')
    r = client.get('/reports/parts-billing')
    assert r.status_code == 200
