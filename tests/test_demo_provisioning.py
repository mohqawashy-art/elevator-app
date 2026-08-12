"""اختبارات إصدار حساب ديمو من لوحة المنصة."""
from datetime import datetime, timedelta

from app import app, db, hash_password
from demo_provisioning import create_demo_account, organization_access_allowed
from models import Customer, Elevator, Fault, MaintenanceVisit, Organization, User


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
        from models import Settings

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
        db.session.commit()
    return app.test_client()


def test_create_demo_account_seeds_four_elevators():
    _client()
    with app.app_context():
        result = create_demo_account(
            company_name='شركة تجربة المصاعد',
            contact_name='عميل محتمل',
            contact_email='prospect@example.com',
            days=5,
            password_hasher=hash_password,
        )
        assert result['ok'] is True
        assert result['username'] == 'demo'
        assert result['password']
        assert result['slug'].startswith('demo-')
        org = db.session.get(Organization, result['organization_id'])
        assert org is not None
        assert org.status == 'trial'
        assert org.elevators_limit_override == 4
        assert org.billing_status == 'complimentary'
        assert '[DEMO]' in (org.notes or '')
        assert Elevator.query.execution_options(skip_tenant=True).filter_by(organization_id=org.id).count() == 4
        assert Customer.query.execution_options(skip_tenant=True).filter_by(organization_id=org.id).count() == 2
        assert MaintenanceVisit.query.execution_options(skip_tenant=True).filter_by(organization_id=org.id).count() == 2
        assert Fault.query.execution_options(skip_tenant=True).filter_by(organization_id=org.id).count() == 1
        user = (
            User.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id, username='demo')
            .first()
        )
        assert user is not None
        assert user.role == 'admin'


def test_organization_access_blocks_expired_trial():
    _client()
    with app.app_context():
        org = Organization(
            slug='expiredemo',
            name='Expired',
            status='trial',
            plan='basic',
            trial_ends_at=datetime.utcnow() - timedelta(hours=1),
        )
        db.session.add(org)
        db.session.commit()
        assert organization_access_allowed(org) is False

        org.trial_ends_at = datetime.utcnow() + timedelta(days=2)
        db.session.commit()
        assert organization_access_allowed(org) is True


def test_platform_demo_create_route_shows_credentials_once():
    client = _client()
    client.post(
        '/login',
        data={'username': 'opsadmin', 'password': 'OpsPass123!'},
        base_url=ADMIN_URL,
    )
    r = client.post(
        '/platform/demos/create',
        data={
            'company_name': 'ديمو مسار المنصة',
            'contact_name': 'تجربة',
            'days': '7',
        },
        base_url=ADMIN_URL,
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    loc = r.headers.get('Location', '')
    assert '/platform/orgs/' in loc

    r2 = client.get(loc, base_url=ADMIN_URL)
    assert r2.status_code == 200
    body = r2.get_data(as_text=True)
    assert 'بيانات الدخول المؤقتة' in body
    assert 'demo' in body
    assert 'كلمة المرور' in body
    assert '4 مصاعد' in body or 'تجريبي' in body

    # مرة ثانية لا تُعرض كلمة المرور من الجلسة
    r3 = client.get(loc, base_url=ADMIN_URL)
    body3 = r3.get_data(as_text=True)
    assert 'بيانات الدخول المؤقتة' not in body3
