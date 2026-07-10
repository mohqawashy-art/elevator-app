"""اختبارات Moyasar checkout / webhook."""
from datetime import datetime, timedelta

from app import app, db, hash_password
from models import Organization, PlatformPayment, Settings, User
from moyasar_payments import apply_moyasar_payment_event
from platform_billing import record_payment


def _setup():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test-secret-key-not-default'
    app.config['SESSION_COOKIE_SECURE'] = False
    with app.app_context():
        db.engine.dispose()
        db.session.remove()
        db.drop_all()
        db.create_all()
        org = Organization(
            slug='payco',
            name='Pay Co',
            status='active',
            plan='basic',
            billing_cycle='monthly',
            billing_status='due',
            current_period_end=datetime.utcnow() - timedelta(days=1),
        )
        db.session.add(org)
        db.session.flush()
        db.session.add(Settings(organization_id=org.id, company_name='Pay Co', tax_pct=15))
        db.session.add(User(
            organization_id=org.id,
            username='payadmin',
            password_hash=hash_password('PayPass123!'),
            full_name='Pay Admin',
            role='admin',
            is_active=True,
        ))
        db.session.commit()
        return org.id


def test_webhook_applies_payment_and_is_idempotent():
    org_id = _setup()
    payload = {
        'id': 'pay_test_abc123',
        'status': 'paid',
        'amount': 29900,
        'currency': 'SAR',
        'metadata': {'organization_id': str(org_id), 'purpose': 'subscription_renewal'},
    }
    with app.app_context():
        r1 = apply_moyasar_payment_event(payload)
        assert r1['ok'] is True
        assert not r1.get('duplicate')
        org = db.session.get(Organization, org_id)
        assert org.billing_status == 'ok'
        assert org.status == 'active'
        assert org.last_payment_ref == 'pay_test_abc123'
        assert PlatformPayment.query.filter_by(reference='pay_test_abc123').count() == 1

        r2 = apply_moyasar_payment_event(payload)
        assert r2['ok'] is True
        assert r2.get('duplicate') is True
        assert PlatformPayment.query.filter_by(reference='pay_test_abc123').count() == 1


def test_record_payment_duplicate_reference():
    org_id = _setup()
    with app.app_context():
        org = db.session.get(Organization, org_id)
        a = record_payment(org, amount=100, method='card', reference='dup-1')
        b = record_payment(org, amount=100, method='card', reference='dup-1')
        assert a['ok'] and b['ok']
        assert b.get('duplicate') is True
        assert PlatformPayment.query.filter_by(reference='dup-1').count() == 1


def test_webhook_endpoint_public(client=None):
    org_id = _setup()
    c = app.test_client()
    r = c.post(
        '/api/webhooks/moyasar',
        json={
            'id': 'pay_http_1',
            'status': 'paid',
            'amount': 29900,
            'metadata': {'organization_id': str(org_id)},
        },
        base_url='https://liftcoreapp.com',
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
