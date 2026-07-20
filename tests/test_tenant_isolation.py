"""اختبارات عزل المستأجر — أسبوع 2–7."""
import pytest

from app import app, db, hash_password
from models import Customer, Organization, User
from tenant_scope import (
    MARKETING_SLUGS,
    _tenant_slug_from_host,
    current_organization_id,
    resolve_tenant,
    tenant_query,
)


@pytest.fixture
def org_a():
    """قاعدة in-memory — لا تلمس instance/*.db ولا تتعارض مع e2e_server."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test-secret-key-not-default'
    app.config['SESSION_COOKIE_SECURE'] = False
    with app.app_context():
        db.engine.dispose()
        db.session.remove()
        db.drop_all()
        db.create_all()
        o = Organization(slug='alpha', name='Alpha Co', status='active')
        db.session.add(o)
        db.session.commit()
        oid = o.id
    return oid


@pytest.fixture
def org_b(org_a):
    with app.app_context():
        o = Organization(slug='beta', name='Beta Co', status='active')
        db.session.add(o)
        db.session.commit()
        return o.id


@pytest.fixture
def tenant_pair(org_a, org_b):
    """مؤسستان + مستخدمان + عميل لكل منهما."""
    with app.app_context():
        user_a = User(
            username='admin',
            password_hash=hash_password('TenantPass99!'),
            full_name='Alpha Admin',
            role='admin',
            is_active=True,
            organization_id=org_a,
        )
        user_b = User(
            username='admin',
            password_hash=hash_password('TenantPass99!'),
            full_name='Beta Admin',
            role='admin',
            is_active=True,
            organization_id=org_b,
        )
        db.session.add_all([user_a, user_b])
        db.session.flush()
        cust_a = Customer(code='C-A100', name='عميل ألفا السري', organization_id=org_a)
        cust_b = Customer(code='C-B100', name='عميل بيتا السري', organization_id=org_b)
        db.session.add_all([cust_a, cust_b])
        db.session.commit()
        return {
            'org_a': org_a,
            'org_b': org_b,
            'user_a': user_a.id,
            'user_b': user_b.id,
            'cust_a': cust_a.id,
            'cust_b': cust_b.id,
            'name_a': cust_a.name,
            'name_b': cust_b.name,
        }


def _tenant_client(user_id: int, base_url: str):
    client = app.test_client()
    app.config['TESTING'] = True
    app.config['SESSION_COOKIE_SECURE'] = False
    with app.app_context():
        user = db.session.get(User, user_id)
        ver = int(getattr(user, 'session_version', None) or 0) if user else 0
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['session_version'] = ver
        sess['lang'] = 'ar'
    return client, base_url


def _tenant_login(client, base_url: str, password: str = 'TenantPass99!'):
  r = client.post(
      '/login',
      data={'username': 'admin', 'password': password},
      base_url=base_url,
      follow_redirects=False,
  )
  assert r.status_code in (302, 303), f'login failed: {r.status_code} {r.location}'
  return client


def test_tenant_a_cannot_see_tenant_b_clients(tenant_pair):
    client, base = _tenant_client(tenant_pair['user_a'], 'https://alpha.liftcoreapp.com')
    _tenant_login(client, base)
    r = client.get('/clients', base_url=base)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'C-A100' in html
    assert 'C-B100' not in html
    assert tenant_pair['name_b'] not in html


def test_cross_tenant_idor_client_edit_returns_404(tenant_pair):
    client, base = _tenant_client(tenant_pair['user_a'], 'https://alpha.liftcoreapp.com')
    _tenant_login(client, base)
    r = client.post(
        f'/clients/edit/{tenant_pair["cust_b"]}',
        data={'name': 'اختراق', 'phone': '512345678', 'status': 'نشط'},
        base_url=base,
        follow_redirects=False,
    )
    assert r.status_code in (403, 404)


def test_user_org_mismatch_on_other_subdomain_aborts(tenant_pair):
    client, base = _tenant_client(tenant_pair['user_a'], 'https://beta.liftcoreapp.com')
    r = client.get('/dashboard', base_url=base, follow_redirects=False)
    assert r.status_code in (302, 403)
    if r.status_code == 302:
        assert 'login' in (r.location or '')


def test_tenant_slug_from_host():
    assert _tenant_slug_from_host('alpha.liftcoreapp.com') == 'alpha'
    assert _tenant_slug_from_host('app.liftcoreapp.com') is None
    assert _tenant_slug_from_host('liftcoreapp.com') is None
    assert _tenant_slug_from_host('127.0.0.1') is None
    assert _tenant_slug_from_host('localhost') is None
    for slug in MARKETING_SLUGS:
        assert _tenant_slug_from_host(f'{slug}.liftcoreapp.com') is None


def test_resolve_tenant_sets_organization(client, org_a):
    with app.app_context():
        org = db.session.get(Organization, org_a)
        assert org is not None
    with app.test_request_context(
        '/dashboard',
        base_url='https://alpha.liftcoreapp.com',
    ):
        resolve_tenant()
        from flask import g

        assert g.organization_id == org_a
        assert g.organization.slug == 'alpha'


def test_resolve_tenant_app_host_uses_default_org(client):
    with app.test_request_context('/', base_url='https://app.liftcoreapp.com'):
        resolve_tenant()
        from flask import g

        assert g.organization_id is not None
        assert g.organization.slug == 'default'


def test_resolve_tenant_root_host_no_org(client):
    with app.test_request_context('/', base_url='https://liftcoreapp.com'):
        resolve_tenant()
        from flask import g

        assert g.organization_id is None
        assert g.organization is None


def test_resolve_tenant_unknown_slug_404(client):
    with app.test_request_context('/', base_url='https://unknown.liftcoreapp.com'):
        with pytest.raises(Exception) as exc:
            resolve_tenant()
        assert getattr(exc.value, 'code', None) == 404


def test_resolve_tenant_suspended_404(client, org_a):
    with app.app_context():
        org = db.session.get(Organization, org_a)
        org.status = 'suspended'
        db.session.commit()
    with app.test_request_context('/', base_url='https://alpha.liftcoreapp.com'):
        with pytest.raises(Exception) as exc:
            resolve_tenant()
        assert getattr(exc.value, 'code', None) == 404


def test_health_exempt_without_tenant(client):
    r = client.get('/api/health', headers={'Host': 'unknown.liftcoreapp.com'})
    assert r.status_code == 200
    assert r.get_json().get('ok') is True


def test_current_organization_id_aborts_without_tenant(client):
    with app.test_request_context('/', base_url='https://liftcoreapp.com'):
        resolve_tenant()
        with pytest.raises(Exception) as exc:
            current_organization_id()
        assert getattr(exc.value, 'code', None) == 404


def test_forgotten_filter_is_still_isolated(org_a, org_b):
    """استعلام خام بدون tenant_query — يجب أن يبقى معزولاً."""
    from models import Customer

    with app.app_context():
        db.session.add(Customer(code='C-A1', name='A1', organization_id=org_a))
        db.session.add(Customer(code='C-B1', name='B1', organization_id=org_b))
        db.session.commit()
    with app.test_request_context(headers={'Host': 'alpha.liftcoreapp.com'}):
        resolve_tenant()
        results = Customer.query.all()
        assert all(c.organization_id == org_a for c in results)


def test_tenant_query_manual_helper(org_a, org_b):
    from models import Customer

    with app.app_context():
        db.session.add(Customer(code='C-A2', name='A2', organization_id=org_a))
        db.session.add(Customer(code='C-B2', name='B2', organization_id=org_b))
        db.session.commit()
    with app.test_request_context(headers={'Host': 'alpha.liftcoreapp.com'}):
        resolve_tenant()
        codes = [c.code for c in tenant_query(Customer).all()]
        assert 'C-A2' in codes
        assert 'C-B2' not in codes


def test_install_lead_isolated_by_tenant(org_a, org_b):
    from installation.models import InstallLead

    with app.app_context():
        db.session.add(InstallLead(code='IL-A1', client_name='A', organization_id=org_a))
        db.session.add(InstallLead(code='IL-B1', client_name='B', organization_id=org_b))
        db.session.commit()
    with app.test_request_context(headers={'Host': 'alpha.liftcoreapp.com'}):
        resolve_tenant()
        codes = [r.code for r in InstallLead.query.all()]
        assert codes == ['IL-A1']
