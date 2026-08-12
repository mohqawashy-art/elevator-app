"""اختبارات لوحة إدارة المنصة admin.liftcoreapp.com."""
from app import app, db, hash_password
from models import Organization, Settings, User


ADMIN_URL = 'https://admin.liftcoreapp.com'
APP_URL = 'https://app.liftcoreapp.com'


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
        other = Organization(slug='acmeco', name='Acme', status='trial', plan='basic', admin_email='a@acme.test')
        db.session.add(other)
        db.session.flush()
        db.session.add(Settings(organization_id=other.id, company_name='Acme', tax_pct=15))
        db.session.add(User(
            organization_id=other.id,
            username='acmeco',
            password_hash=hash_password('AcmePass123!'),
            full_name='Acme Admin',
            email='a@acme.test',
            role='admin',
            is_active=True,
        ))
        db.session.commit()
    return app.test_client()


def test_admin_host_login_and_home():
    client = _client()
    r = client.get('/platform', base_url=ADMIN_URL, follow_redirects=False)
    assert r.status_code in (302, 401)
    r = client.post(
        '/login',
        data={'username': 'opsadmin', 'password': 'OpsPass123!'},
        base_url=ADMIN_URL,
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    r = client.get('/platform', base_url=ADMIN_URL)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'لوحة إدارة المنصة' in body
    assert 'Acme' in body
    assert 'liftcore-header-logo.png' in body or 'liftcore-brand-logo.png' in body
    assert 'PLATFORM' in body or 'Platform Admin' in body or 'إدارة المنصة' in body


def test_platform_leads_page_shows_sales_request():
    from models import SalesLead

    client = _client()
    with app.app_context():
        db.session.add(SalesLead(
            request_type='demo',
            status='new',
            company_name='شركة مكة للصيانة',
            contact_name='أحمد',
            contact_email='ahmad@example.com',
            phone='0566299626',
            city='مكة المكرمة',
            elevators='20',
            source_path='/',
            email_sent=True,
        ))
        db.session.commit()

    client.post(
        '/login',
        data={'username': 'opsadmin', 'password': 'OpsPass123!'},
        base_url=ADMIN_URL,
        follow_redirects=False,
    )
    r = client.get('/platform/leads', base_url=ADMIN_URL)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'طلبات التجربة' in body or 'طلبات المبيعات' in body
    assert 'شركة مكة للصيانة' in body
    assert 'ahmad@example.com' in body
    assert 'موافق — إرسال تجربة' in body


def test_platform_send_quote_button(monkeypatch):
    from models import SalesLead

    sent = {}

    def fake_quote(**kwargs):
        sent.update(kwargs)
        return {'ok': True, 'reason': 'sent'}

    monkeypatch.setattr('liftcore_mail.send_pricing_quote_email', fake_quote)

    client = _client()
    with app.app_context():
        lead = SalesLead(
            request_type='quote',
            status='new',
            company_name='شركة عرض',
            contact_name='سارة',
            contact_email='sara@example.com',
            elevators='40',
        )
        db.session.add(lead)
        db.session.commit()
        lid = lead.id

    client.post(
        '/login',
        data={'username': 'opsadmin', 'password': 'OpsPass123!'},
        base_url=ADMIN_URL,
    )
    r = client.post(f'/platform/leads/{lid}/send-quote', base_url=ADMIN_URL, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert sent.get('to_email') == 'sara@example.com'
    with app.app_context():
        lead = db.session.get(SalesLead, lid)
        assert lead.status == 'fulfilled'
        assert lead.customer_mail_sent is True


def test_tenant_user_cannot_use_admin_console():
    client = _client()
    r = client.post(
        '/login',
        data={'username': 'acmeco', 'password': 'AcmePass123!'},
        base_url=ADMIN_URL,
        follow_redirects=True,
    )
    body = r.get_data(as_text=True)
    assert 'غير مخوّل' in body or 'غير صحيحة' in body or r.request.path.endswith('/login')


def test_platform_org_detail_and_suspend():
    client = _client()
    client.post(
        '/login',
        data={'username': 'opsadmin', 'password': 'OpsPass123!'},
        base_url=ADMIN_URL,
    )
    with app.app_context():
        org = Organization.query.filter_by(slug='acmeco').first()
        oid = org.id
    r = client.get(f'/platform/orgs/{oid}', base_url=ADMIN_URL)
    assert r.status_code == 200
    assert 'Acme' in r.get_data(as_text=True)

    r = client.post(
        f'/platform/orgs/{oid}/update',
        data={'name': 'Acme', 'plan': 'pro', 'status': 'suspended', 'notes': 'test'},
        base_url=ADMIN_URL,
        follow_redirects=True,
    )
    assert r.status_code == 200
    with app.app_context():
        org = db.session.get(Organization, oid)
        assert org.status == 'suspended'
        assert org.plan == 'pro'


def test_platform_routes_404_on_app_host():
    client = _client()
    client.post(
        '/login',
        data={'username': 'opsadmin', 'password': 'OpsPass123!'},
        base_url=APP_URL,
    )
    r = client.get('/platform', base_url=APP_URL)
    assert r.status_code == 404


def test_platform_org_export_download():
    import io
    import json
    import zipfile

    from models import Customer, ZatcaCredentials

    client = _client()
    client.post(
        '/login',
        data={'username': 'opsadmin', 'password': 'OpsPass123!'},
        base_url=ADMIN_URL,
    )
    with app.app_context():
        org = Organization.query.filter_by(slug='acmeco').first()
        oid = org.id
        db.session.add(Customer(
            organization_id=oid,
            code='C-1',
            name='عميل تجريبي',
        ))
        z = ZatcaCredentials.query.filter_by(organization_id=oid).first()
        if not z:
            z = ZatcaCredentials(
                organization_id=oid,
                vat_number='300000000000003',
                status='active',
            )
            db.session.add(z)
        z.private_key = 'SECRET-PRIVATE-KEY'
        z.api_secret = 'SECRET-API'
        z.csid = 'SECRET-CSID'
        z.certificate = 'SECRET-CERT'
        db.session.commit()

    r = client.get(f'/platform/orgs/{oid}/export', base_url=ADMIN_URL)
    assert r.status_code == 200
    assert r.mimetype == 'application/zip'
    assert 'attachment' in (r.headers.get('Content-Disposition') or '')
    assert r.data[:2] == b'PK'

    with zipfile.ZipFile(io.BytesIO(r.data)) as zf:
        names = zf.namelist()
        json_name = next(n for n in names if n.endswith('-data.json'))
        payload = json.loads(zf.read(json_name).decode('utf-8'))

    assert payload.get('version') == 2
    assert 'password_hash' in (payload.get('security') or {}).get('redacted_fields', {}).get('users', [])

    users = payload['tables'].get('users') or []
    assert users
    for u in users:
        assert u.get('password_hash') == '[REDACTED]'
        assert 'pbkdf2' not in str(u.get('password_hash'))
        assert u.get('password_hash_was_set') is True

    creds = payload['tables'].get('zatca_credentials') or []
    assert creds
    for row in creds:
        assert row.get('private_key') == '[REDACTED]'
        assert row.get('api_secret') == '[REDACTED]'
        assert row.get('csid') == '[REDACTED]'
        assert row.get('certificate') == '[REDACTED]'
        assert 'SECRET-' not in json.dumps(row)


def test_sanitize_export_row_unit():
    from tenant_lifecycle import EXPORT_REDACT_MARKER, _sanitize_export_row

    out = _sanitize_export_row('users', {
        'username': 'admin',
        'password_hash': 'pbkdf2:sha256:...',
        'role': 'admin',
    })
    assert out['username'] == 'admin'
    assert out['password_hash'] == EXPORT_REDACT_MARKER
    assert out['password_hash_was_set'] is True

    empty = _sanitize_export_row('technicians', {'sign_pin_hash': None, 'name': 'فني'})
    assert empty['sign_pin_hash'] is None
    assert empty['sign_pin_hash_was_set'] is False


def test_platform_org_delete_requires_confirm_and_password():
    from models import Customer

    client = _client()
    client.post(
        '/login',
        data={'username': 'opsadmin', 'password': 'OpsPass123!'},
        base_url=ADMIN_URL,
    )
    with app.app_context():
        org = Organization.query.filter_by(slug='acmeco').first()
        oid = org.id
        db.session.add(Customer(organization_id=oid, code='C-DEL', name='للحذف'))
        db.session.commit()

    # wrong slug
    r = client.post(
        f'/platform/orgs/{oid}/delete',
        data={
            'confirm_slug': 'wrong',
            'confirm_phrase': 'DELETE',
            'admin_password': 'OpsPass123!',
            'acknowledge': '1',
        },
        base_url=ADMIN_URL,
        follow_redirects=True,
    )
    assert r.status_code == 200
    with app.app_context():
        assert Organization.query.filter_by(slug='acmeco').first() is not None

    # success
    r = client.post(
        f'/platform/orgs/{oid}/delete',
        data={
            'confirm_slug': 'acmeco',
            'confirm_phrase': 'DELETE',
            'admin_password': 'OpsPass123!',
            'acknowledge': '1',
        },
        base_url=ADMIN_URL,
        follow_redirects=True,
    )
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'تم إلغاء العميل' in body or 'مسح' in body
    with app.app_context():
        assert Organization.query.filter_by(slug='acmeco').first() is None
        assert Customer.query.filter_by(code='C-DEL').count() == 0


def test_platform_cannot_delete_operator_org():
    client = _client()
    client.post(
        '/login',
        data={'username': 'opsadmin', 'password': 'OpsPass123!'},
        base_url=ADMIN_URL,
    )
    with app.app_context():
        org = Organization.query.filter_by(slug='default').first()
        oid = org.id
    r = client.post(
        f'/platform/orgs/{oid}/delete',
        data={
            'confirm_slug': 'default',
            'confirm_phrase': 'DELETE',
            'admin_password': 'OpsPass123!',
            'acknowledge': '1',
        },
        base_url=ADMIN_URL,
        follow_redirects=True,
    )
    assert r.status_code == 200
    with app.app_context():
        assert Organization.query.filter_by(slug='default').first() is not None
