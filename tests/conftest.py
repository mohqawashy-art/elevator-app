"""Fixtures مشتركة — قاعدة in-memory لكل اختبار."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# قبل استيراد app: تجنّب مزامنة startup على قاعدة محلية/إنتاج وتهيئة SQLite نظيفة للاختبار
os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-default')
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['LIFTCORE_ALEMBIC'] = '1'  # تخطّي _startup_schema_and_data_sync عند الاستيراد
os.environ.pop('LIFTCORE_HTTPS', None)

from app import app, db, hash_password
from models import Organization, Settings, User, ZatcaCredentials


def _default_org_id():
    org = Organization.query.filter_by(slug='default').first()
    if not org:
        org = Organization(slug='default', name='Test Org', status='active', plan='pro')
        db.session.add(org)
        db.session.commit()
    elif not getattr(org, 'plan', None):
        org.plan = 'pro'
        db.session.commit()
    return org.id


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test-secret-key-not-default'
    app.config['SESSION_COOKIE_SECURE'] = False
    with app.app_context():
        db.engine.dispose()
        db.session.remove()
        db.drop_all()
        db.create_all()
        org_id = _default_org_id()
        if not Settings.query.first():
            db.session.add(Settings(company_name='LiftCore Test', tax_pct=15, organization_id=org_id))
        if not ZatcaCredentials.query.filter_by(organization_id=org_id).first():
            db.session.add(ZatcaCredentials(
                organization_id=org_id,
                vat_number='300000000000003',
                status='active',
            ))
        users = {}
        for role in ('admin', 'manager', 'viewer'):
            u = User(
                username=f'test_{role}',
                password_hash=hash_password('TestPass123!'),
                full_name=role,
                role=role,
                is_active=True,
                organization_id=org_id,
            )
            db.session.add(u)
            users[role] = u
        db.session.commit()
        user_ids = {role: users[role].id for role in users}
    with app.test_client() as c:
        c._user_ids = user_ids
        yield c


def login_as(client, role: str = 'admin'):
    uid = client._user_ids[role]
    with app.app_context():
        user = db.session.get(User, uid)
        ver = int(getattr(user, 'session_version', None) or 0) if user else 0
    with client.session_transaction() as sess:
        sess['user_id'] = uid
        sess['session_version'] = ver
        sess['lang'] = 'ar'


def ensure_test_organization():
    """مؤسسة افتراضية للاختبارات التي تنشئ جداولها يدوياً."""
    org = Organization.query.filter_by(slug='default').first()
    if not org:
        org = Organization(slug='default', name='Test Org', status='active', plan='pro')
        db.session.add(org)
        db.session.commit()
    return org.id
