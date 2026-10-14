"""اختبارات اشتراكات لوحة المنصة (يدوي)."""
from datetime import datetime, timedelta

from app import app, db, hash_password
from models import Organization, PlatformExpense, PlatformInvoice, PlatformPayment, Settings, User
from platform_billing import (
    account_statement,
    add_expense,
    apply_free_tenant_policy,
    books_snapshot,
    effective_amount,
    extend_trial,
    issue_invoice,
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
    assert plan_price('liftcore', 'monthly') == round(2399 / 12, 2)
    assert plan_price('liftcore', 'yearly') == 2399.0
    assert plan_price('basic', 'monthly') == round(2399 / 12, 2)
    assert plan_price('enterprise', 'yearly') == 2399.0


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
        assert effective_amount(org) == round(2399 / 12, 2)


def test_jama_and_demo_are_free_and_zero_revenue():
    client = _client()
    with app.app_context():
        jama = Organization(slug='jama', name='جما', status='active', plan='liftcore')
        demo = Organization(slug='demo', name='Demo', status='trial', plan='basic', notes='[DEMO] trial')
        db.session.add_all([jama, demo])
        db.session.commit()
        db.session.add(PlatformPayment(organization_id=jama.id, amount=2399, method='transfer', reference='OLD-JAMA'))
        db.session.add(PlatformPayment(organization_id=demo.id, amount=199, method='transfer', reference='OLD-DEMO'))
        db.session.commit()

        apply_free_tenant_policy(jama)
        apply_free_tenant_policy(demo)
        db.session.commit()

        jama = Organization.query.filter_by(slug='jama').first()
        demo = Organization.query.filter_by(slug='demo').first()
        assert jama.billing_status == 'complimentary'
        assert demo.billing_status == 'complimentary'
        assert effective_amount(jama) == 0
        assert effective_amount(demo) == 0
        assert jama.current_period_end is not None
        assert PlatformPayment.query.filter_by(organization_id=jama.id).first().amount == 0
        assert PlatformPayment.query.filter_by(organization_id=demo.id).first().amount == 0

        paid = record_payment(jama, amount=2399, method='transfer', reference='TRY-JAMA')
        assert paid['ok']
        assert paid['payment'].amount == 0
        assert paid['payment'].method == 'complimentary'

        denied = issue_invoice(jama, amount=2399)
        assert not denied['ok']

        books = books_snapshot(year=datetime.utcnow().year)
        assert books['revenue'] == 0


def test_invoice_receipt_statement_and_pnl():
    client = _client()
    with app.app_context():
        org = Organization.query.filter_by(slug='billco').first()
        issued = issue_invoice(org, amount=2399, description='اشتراك سنوي')
        assert issued['ok']
        inv = issued['invoice']
        assert inv.code.startswith('NSQ-INV-')
        assert inv.status == 'unpaid'
        assert abs(inv.total - 2399) < 0.01
        assert inv.tax_amount > 0

        paid = record_payment(org, amount=2399, method='transfer', reference='BANK-INV', invoice_id=inv.id)
        assert paid['ok']
        assert paid['payment'].receipt_code.startswith('NSQ-RCP-')
        inv = db.session.get(PlatformInvoice, inv.id)
        assert inv.status == 'paid'

        st = account_statement(org)
        assert st['debit'] == 2399
        assert st['credit'] == 2399
        assert st['balance'] == 0

        exp = add_expense(amount=400, description='استضافة Hetzner', category='hosting')
        assert exp['ok']
        books = books_snapshot(year=datetime.utcnow().year)
        assert books['revenue'] == 2399
        assert books['expenses'] == 400
        assert books['net'] == 1999


def test_invoice_print_has_nasaq_letterhead():
    client = _client()
    _login(client)
    r = client.get('/platform/invoices/sample', base_url=ADMIN_URL)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'nasaq-core-logo.png' in body
    assert '4031239017' in body
    assert 'حي العوالي' in body
    assert 'طريق الطائف' in body
    assert 'info@liftcoreapp.com' in body
    assert 'مؤسسة نسق كور' in body
    assert '<div class="t">فاتورة</div>' in body
    assert 'TAX INVOICE' not in body
    assert 'ضريبة القيمة المضافة' not in body


def test_billing_page_shows_nasq_core_books():
    client = _client()
    _login(client)
    r = client.get('/platform/billing', base_url=ADMIN_URL)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'نسق كور' in body
    assert 'بيان الأرباح' in body
    assert 'Bill Co' in body
