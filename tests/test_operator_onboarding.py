"""اختبارات دعوات الانضمام + تفعيل المشغّل."""
import pytest

from app import app, db, hash_password
from models import OnboardingInvite, Organization, Settings, User
from operator_onboarding import activate_invite, create_invite, submit_invite_form


ROOT_URL = 'https://liftcoreapp.com'
APP_URL = 'https://app.liftcoreapp.com'


@pytest.fixture
def ob_client():
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
        db.session.commit()
    with app.test_client() as client:
        yield client


def _login_ops(client):
    return client.post(
        '/login',
        data={'username': 'opsadmin', 'password': 'OpsPass123!'},
        base_url=APP_URL,
        follow_redirects=False,
    )


def test_create_invite_and_public_form(ob_client):
    with app.app_context():
        result = create_invite(plan='pro', suggested_slug='acmeco', contact_email='a@acme.test')
        assert result['ok']
        token = result['invite'].token

    r = ob_client.get(f'/onboard/{token}', base_url=ROOT_URL)
    assert r.status_code == 200
    assert 'بيانات الشركة' in r.get_data(as_text=True)

    r = ob_client.post(
        f'/onboard/{token}',
        data={
            'company_name': 'شركة أكمي',
            'company_name_en': 'Acme Co',
            'cr_number': '1010101010',
            'vat_number': '300000000000003',
            'preferred_slug': 'acmeco',
            'admin_name': 'أحمد',
            'admin_email': 'admin@acme.test',
            'city': 'الرياض',
        },
        base_url=ROOT_URL,
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert 'تم استلام' in r.get_data(as_text=True)

    with app.app_context():
        inv = OnboardingInvite.query.filter_by(token=token).first()
        assert inv.status == 'submitted'
        assert inv.company_name == 'شركة أكمي'


def test_onboard_on_tenant_host_404(ob_client):
    with app.app_context():
        token = create_invite()['invite'].token
    r = ob_client.get(f'/onboard/{token}', base_url='https://alpha.liftcoreapp.com')
    assert r.status_code == 404


def test_activate_creates_active_org(ob_client):
    with app.app_context():
        inv = create_invite(plan='basic', suggested_slug='betaorg')['invite']
        submit_invite_form(inv, {
            'company_name': 'بيتا',
            'preferred_slug': 'betaorg',
            'admin_name': 'سارة',
            'admin_email': 's@beta.test',
            'vat_number': '300000000000003',
            'cr_number': '123',
        })
        inv = db.session.get(OnboardingInvite, inv.id)
        result = activate_invite(
            inv,
            slug='betaorg',
            plan='pro',
            password='BetaPass123!',
            password_hash=hash_password('BetaPass123!'),
        )
        assert result['ok'], result
        org = Organization.query.filter_by(slug='betaorg').first()
        assert org is not None
        assert org.status == 'active'
        assert org.plan == 'pro'
        from flask import g
        g._resolving_default_org = True
        settings = Settings.query.filter_by(organization_id=org.id).first()
        assert settings is not None
        assert settings.vat_number == '300000000000003'
        user = User.query.filter_by(organization_id=org.id, username='betaorg').first()
        assert user is not None
        inv2 = db.session.get(OnboardingInvite, inv.id)
        assert inv2.status == 'activated'


def test_operator_panel_requires_default_admin(ob_client):
    r = ob_client.get('/operator/onboarding', base_url=APP_URL)
    assert r.status_code in (302, 401)

    _login_ops(ob_client)
    r = ob_client.get('/operator/onboarding', base_url=APP_URL)
    assert r.status_code == 200
    assert 'دعوات انضمام' in r.get_data(as_text=True)


def test_operator_create_via_post(ob_client):
    _login_ops(ob_client)
    r = ob_client.post(
        '/operator/onboarding/create',
        data={
            'plan': 'enterprise',
            'suggested_slug': 'gamma',
            'contact_name': 'علي',
            'contact_email': 'ali@gamma.test',
            'days': '7',
        },
        base_url=APP_URL,
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert 'رابط الدعوة' in r.get_data(as_text=True)
    with app.app_context():
        inv = OnboardingInvite.query.filter_by(suggested_slug='gamma').first()
        assert inv is not None
        assert inv.plan == 'enterprise'
