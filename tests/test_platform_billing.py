"""اختبارات اشتراكات لوحة المنصة (يدوي)."""
from datetime import datetime, timedelta

from app import app, db, hash_password
from models import Organization, PlatformPayment, Settings, User
from platform_billing import (
    effective_amount,
    extend_trial,
    plan_price,
    record_payment,
    refresh_billing_status,
)


ADMIN_URL = 'https://admin.liftcoreapp.com'


def _client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test-secret-key-not-default'
    app.config['SESSION_COOKIE_SECURE'] = False
    with app.app_context():
        db.engine.dispose()
        db.session.remove()
        db.drop_all()
        db.create_all()
        org = Organization(slug='default', name='LiftCore Ops', status='active', plan='enterprise')
        db.session.add(org)
        db.session.flush()
        db.session.add(Settings(organization_id=org.id, company_name='LiftCore Ops', tax_pct=15))
        db.session.add(User(
            organization_id=org.id,
            username='opsadmin',
            password_hash=hash_password('OpsPass123!'),
            full_name='Ops Admin',
            email='ops@liftcoreapp.com',
            role='admin',
            is_active=True,
        ))
        client_org = Organization(
            slug='billco',
            name='Bill Co',
            status='trial',
            plan='basic',
            admin_email='b@bill.test',
            trial_ends_at=datetime.utcnow() + timedelta(days=3),
            billing_cycle='monthly',
            billing_status='due',
        )
        db.session.add(client_org)
        db.session.commit()
    return app.test_client()


def _login(client):
    return client.post(
        '/login',
        data={'username': 'opsadmin', 'password': 'OpsPass123!'},
        base_url=ADMIN_URL,
        follow_redirects=False,
    )


def test_plan_prices():
    assert plan_price('basic', 'monthly') == 250.0
    assert plan_price('plus', 'yearly') == 4590.0
    assert plan_price('pro', 'yearly') == 5400.0
    assert plan_price('enterprise', 'monthly') == 1000.0


def test_record_payment_extends_period():
    client = _client()
    with app.app_context():
        org = Organization.query.filter_by(slug='billco').first()
        result = record_payment(org, amount=299, months=1, method='transfer', reference='TRX-1')
        assert result['ok']
        org = db.session.get(Organization, org.id)
        assert org.status == 'active'
        assert org.billing_status == 'ok'
        assert org.current_period_end is not None
        assert org.last_payment_amount == 299
        assert PlatformPayment.query.filter_by(organization_id=org.id).count() == 1


def test_extend_trial():
    client = _client()
    with app.app_context():
        org = Organization.query.filter_by(slug='billco').first()
        before = org.trial_ends_at
        result = extend_trial(org, days=10)
        assert result['ok']
        assert org.trial_ends_at > before
        assert org.status == 'trial'


def test_billing_page_and_payment_post():
    client = _client()
    _login(client)
    r = client.get('/platform/billing', base_url=ADMIN_URL)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'اشتراكات' in body
    assert 'Bill Co' in body

    with app.app_context():
        oid = Organization.query.filter_by(slug='billco').first().id

    r = client.post(
        f'/platform/orgs/{oid}/payment',
        data={'amount': '599', 'months': '2', 'method': 'transfer', 'reference': 'BANK-9'},
        base_url=ADMIN_URL,
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert 'تم تسجيل الدفعة' in r.get_data(as_text=True) or 'Bill Co' in r.get_data(as_text=True)
    with app.app_context():
        org = Organization.query.filter_by(slug='billco').first()
        assert org.status == 'active'
        assert org.last_payment_ref == 'BANK-9'
        assert PlatformPayment.query.filter_by(organization_id=org.id).count() == 1


def test_refresh_overdue():
    client = _client()
    with app.app_context():
        org = Organization.query.filter_by(slug='billco').first()
        org.status = 'active'
        org.current_period_end = datetime.utcnow() - timedelta(days=20)
        org.billing_status = 'ok'
        status = refresh_billing_status(org, commit=True)
        assert status == 'overdue'
        assert effective_amount(org) == 299.0
