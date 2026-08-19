"""بوابة الأقسام — ظهور الأقسام والروابط حسب الصلاحيات."""
from __future__ import annotations

from liftcore_permissions import dump_permissions_extra
from models import User, db
from tests.conftest import login_as


def test_home_requires_login(client):
    response = client.get('/home', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in (response.headers.get('Location') or '')


def test_admin_sees_all_department_cards_and_sidebar_home(client):
    login_as(client, 'admin')
    response = client.get('/home')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for title in (
        'الصيانة والأعطال',
        'التركيبات والتحديث',
        'المخازن والمشتريات',
        'شؤون العاملين والفنيين',
        'الحسابات والمالية',
    ):
        assert title in html
    assert 'href="/home"' in html
    assert 'href="/dashboard"' in html


def test_custom_finance_user_only_sees_authorized_department(client):
    with client.application.app_context():
        user = db.session.get(User, client._user_ids['viewer'])
        user.role = 'custom'
        user.permissions_extra = dump_permissions_extra([
            'revenues.read',
            'report_revenues.read',
        ])
        db.session.commit()

    login_as(client, 'viewer')
    response = client.get('/home')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'الحسابات والمالية' in html
    assert 'href="/revenues"' in html
    assert 'href="/reports/revenues"' in html
    assert 'الصيانة والأعطال' not in html
    assert 'المخازن والمشتريات' not in html
    assert 'التركيبات والتحديث' not in html
    assert 'شؤون العاملين والفنيين' not in html
    assert 'href="/expenses"' not in html
    assert 'href="/reports/expenses"' not in html


def test_custom_user_without_grants_gets_safe_empty_state(client):
    with client.application.app_context():
        user = db.session.get(User, client._user_ids['viewer'])
        user.role = 'custom'
        user.permissions_extra = dump_permissions_extra([])
        db.session.commit()

    login_as(client, 'viewer')
    response = client.get('/home')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'لا توجد أقسام متاحة لصلاحيات حسابك' in html
    assert 'href="/dashboard"' not in html


def test_authenticated_root_redirects_to_home(client):
    base_url = 'https://app.liftcoreapp.com'
    with client.application.app_context():
        user = db.session.get(User, client._user_ids['admin'])
        session_version = int(user.session_version or 0)
    with client.session_transaction(base_url=base_url) as session:
        session['user_id'] = user.id
        session['session_version'] = session_version
        session['lang'] = 'ar'
    response = client.get(
        '/',
        base_url=base_url,
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert '/home' in (response.headers.get('Location') or '')
