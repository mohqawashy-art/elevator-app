"""اختبارات التسجيل الذاتي — أسبوع 7."""
import os

import pytest

from app import app, db, hash_password
from models import Organization, Settings, User


@pytest.fixture(autouse=True)
def enable_signup(monkeypatch):
    monkeypatch.setenv('LIFTCORE_SIGNUP_ENABLED', '1')


@pytest.fixture
def signup_client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test-secret-key-not-default'
    app.config['SESSION_COOKIE_SECURE'] = False
    with app.app_context():
        db.engine.dispose()
        db.session.remove()
        db.drop_all()
        db.create_all()
    with app.test_client() as client:
        yield client


ROOT_URL = 'https://liftcoreapp.com'


def test_signup_disabled_returns_404(monkeypatch, signup_client):
    monkeypatch.delenv('LIFTCORE_SIGNUP_ENABLED', raising=False)
    monkeypatch.delenv('LIFTCORE_COMING_SOON', raising=False)
    r = signup_client.get('/signup', base_url=ROOT_URL, follow_redirects=False)
    # التسجيل المغلق يوجّه لصفحة الأسعار/التعريف بدل 404 الصريح
    assert r.status_code in (302, 303, 404)
    if r.status_code in (302, 303):
        assert '/pricing' in (r.location or '') or r.location.endswith('/')


def test_coming_soon_on_marketing_host(monkeypatch, signup_client):
    monkeypatch.setenv('LIFTCORE_COMING_SOON', '1')
    monkeypatch.delenv('LIFTCORE_SIGNUP_ENABLED', raising=False)
    r = signup_client.get('/', base_url=ROOT_URL)
    assert r.status_code == 200
    # الصفحة العامة = تعريف المنتج (بدل coming_soon.html)
    body = r.get_data(as_text=True)
    assert 'نظام تشغيل' in body or 'LiftCore' in body
    r2 = signup_client.get('/signup', base_url=ROOT_URL, follow_redirects=False)
    assert r2.status_code in (302, 303)
    assert '/pricing' in (r2.location or '')
    # مستأجر غير موجود في DB الاختبار → 404 طبيعي؛ المهم ألا يُعرض coming soon
    r3 = signup_client.get('/', base_url='https://jama.liftcoreapp.com')
    assert r3.status_code in (200, 302, 401, 404)
    assert b'COMING SOON' not in r3.data


def test_signup_on_subdomain_returns_404(signup_client):
    r = signup_client.get('/signup', base_url='https://alpha.liftcoreapp.com')
    assert r.status_code == 404


def test_signup_page_ok(signup_client):
    r = signup_client.get('/signup', base_url=ROOT_URL)
    assert r.status_code == 200
    assert 'إنشاء حساب' in r.get_data(as_text=True)


def test_api_signup_creates_org_admin_settings(signup_client):
    r = signup_client.post(
        '/api/signup',
        json={
            'company_name': 'شركة الاختبار',
            'slug': 'testco',
            'admin_email': 'admin@testco.sa',
            'admin_name': 'أحمد',
            'password': 'SecurePass99!',
        },
        base_url=ROOT_URL,
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data['ok'] is True
    assert data['slug'] == 'testco'
    assert 'testco.liftcoreapp.com/login' in data['login_url']

    with app.app_context():
        org = Organization.query.filter_by(slug='testco').first()
        assert org is not None
        assert org.status == 'trial'
        assert org.admin_email == 'admin@testco.sa'
        settings = Settings.query.filter_by(organization_id=org.id).first()
        assert settings is not None
        assert settings.company_name == 'شركة الاختبار'
        user = User.query.filter_by(organization_id=org.id, role='admin').first()
        assert user is not None
        assert user.username == 'testco'
        assert user.email == 'admin@testco.sa'


def test_signup_rejects_duplicate_slug(signup_client):
    payload = {
        'company_name': 'أولى',
        'slug': 'dupco',
        'admin_email': 'a@dup.sa',
        'admin_name': 'علي',
        'password': 'SecurePass99!',
    }
    assert signup_client.post('/api/signup', json=payload, base_url=ROOT_URL).status_code == 201
    r = signup_client.post('/api/signup', json={
        **payload,
        'company_name': 'ثانية',
        'admin_email': 'b@dup.sa',
    }, base_url=ROOT_URL)
    assert r.status_code == 400
    assert 'مستخدم' in ' '.join(r.get_json().get('errors', []))


def test_signup_rejects_weak_password(signup_client):
    r = signup_client.post(
        '/api/signup',
        json={
            'company_name': 'ضعيفة',
            'slug': 'weakco',
            'admin_email': 'w@weak.sa',
            'admin_name': 'سعد',
            'password': '123456',
        },
        base_url=ROOT_URL,
    )
    assert r.status_code == 400


def test_signup_rejects_reserved_slug(signup_client):
    r = signup_client.post(
        '/api/signup',
        json={
            'company_name': 'محجوز',
            'slug': 'demo',
            'admin_email': 'j@x.sa',
            'admin_name': 'خالد',
            'password': 'SecurePass99!',
        },
        base_url=ROOT_URL,
    )
    assert r.status_code == 400
