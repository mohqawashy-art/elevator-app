"""دخول المنصة: منشأة + مستخدم + كلمة مرور."""
import os

import pytest

from app import app, db, hash_password
from models import Organization, Settings, User


@pytest.fixture
def portal_client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test-secret-key-not-default'
    app.config['SESSION_COOKIE_SECURE'] = False
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        org = Organization(slug='acme', name='شركة أكمي', status='active')
        db.session.add(org)
        db.session.flush()
        db.session.add(Settings(
            organization_id=org.id,
            company_name='شركة أكمي',
        ))
        db.session.add(User(
            organization_id=org.id,
            username='acme',
            password_hash=hash_password('SecurePass99!'),
            full_name='مدير أكمي',
            role='admin',
            is_active=True,
        ))
        db.session.commit()
    with app.test_client() as client:
        yield client


def test_platform_login_shows_org_field(portal_client):
    r = portal_client.get('/login', base_url='https://liftcoreapp.com')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'name="organization"' in html
    assert 'اسم المنشأة' in html


def test_platform_login_redirects_to_tenant_handoff(portal_client):
    r = portal_client.post(
        '/login',
        base_url='https://liftcoreapp.com',
        data={
            'organization': 'acme',
            'username': 'acme',
            'password': 'SecurePass99!',
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    loc = r.headers.get('Location', '')
    assert 'acme.liftcoreapp.com/auth/handoff' in loc
    assert 't=' in loc


def test_platform_login_accepts_company_name(portal_client):
    r = portal_client.post(
        '/login',
        base_url='https://liftcoreapp.com',
        data={
            'organization': 'شركة أكمي',
            'username': 'acme',
            'password': 'SecurePass99!',
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert 'acme.liftcoreapp.com/auth/handoff' in r.headers.get('Location', '')


def test_tenant_login_unchanged(portal_client):
    r = portal_client.get('/login', base_url='https://acme.liftcoreapp.com')
    assert r.status_code == 200
    assert 'name="organization"' not in r.get_data(as_text=True)
