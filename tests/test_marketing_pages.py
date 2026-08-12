"""اختبارات صفحات التسويق العامة."""
from app import app


PUBLIC = 'https://liftcoreapp.com'
APP = 'https://app.liftcoreapp.com'


def test_public_landing_and_pricing_anonymous():
    client = app.test_client()
    app.config['TESTING'] = True

    r = client.get('/', base_url=PUBLIC)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'LiftCore' in body
    assert 'صيانة المصاعد' in body
    assert '/pricing' in body
    assert 'images/marketing/screens/dashboard.png' in body
    assert 'خريطة المصاعد' in body
    assert 'زيارات الصيانة' in body
    assert 'sales@liftcoreapp.com' in body
    assert 'طلب عرض تجريبي' in body or 'اطلب عرضاً تجريبياً' in body
    assert 'demo-request' in body or 'إرسال طلب التجربة' in body
    assert 'name="contact_email"' in body
    assert '#contact' in body

    r = client.get('/pricing', base_url=PUBLIC)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'Basic' in body
    assert 'Plus' in body
    assert '3,000' in body or '3000' in body
    assert 'ر.س' in body
    assert 'login' not in (r.headers.get('Location') or '').lower()
    assert 'إرسال طلب التجربة' in body


def test_robots_and_sitemap_public():
    client = app.test_client()
    app.config['TESTING'] = True
    r = client.get('/robots.txt', base_url=PUBLIC)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'Sitemap: https://liftcoreapp.com/sitemap.xml' in body
    assert 'Disallow: /platform' in body
    assert 'Allow: /start' in body

    r = client.get('/sitemap.xml', base_url=PUBLIC)
    assert r.status_code == 200
    xml = r.get_data(as_text=True)
    assert 'https://liftcoreapp.com/' in xml
    assert 'https://liftcoreapp.com/pricing' in xml
    assert 'https://liftcoreapp.com/start' in xml

    r = client.get('/googled3a45657a209d04b.html', base_url=PUBLIC)
    assert r.status_code == 200
    assert 'google-site-verification: googled3a45657a209d04b.html' in r.get_data(as_text=True)


def test_demo_request_posts_to_sales_mail(monkeypatch):
    captured = {}

    def fake_send(**kwargs):
        captured.update(kwargs)
        return {'ok': True, 'reason': 'sent'}

    monkeypatch.setattr('liftcore_mail.send_demo_request_email', fake_send)

    client = app.test_client()
    app.config['TESTING'] = True
    with app.app_context():
        from models import SalesLead, db
        db.create_all()

    r = client.post(
        '/demo-request',
        data={
            'company_name': 'شركة تجربة',
            'contact_name': 'محمد',
            'contact_email': 'buyer@example.com',
            'phone': '0566299626',
            'city': 'مكة المكرمة',
            'elevators': '12',
            'notes': 'باقة Plus',
            'request_type': 'quote',
            'next': '/',
        },
        base_url=PUBLIC,
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert '#contact' in (r.headers.get('Location') or '')
    assert captured.get('company_name') == 'شركة تجربة'
    assert captured.get('contact_email') == 'buyer@example.com'
    assert captured.get('request_type') == 'quote'
    assert 'sales@' in (captured.get('sales_email') or '')

    with app.app_context():
        from models import SalesLead
        lead = SalesLead.query.filter_by(contact_email='buyer@example.com').order_by(SalesLead.id.desc()).first()
        assert lead is not None
        assert lead.company_name == 'شركة تجربة'
        assert lead.request_type == 'quote'
        assert lead.email_sent is True
        assert lead.status == 'new'


def test_ads_landing_and_conversion_flow(monkeypatch):
    monkeypatch.setattr(
        'liftcore_mail.send_demo_request_email',
        lambda **kwargs: {'ok': True, 'reason': 'sent'},
    )
    client = app.test_client()
    app.config['TESTING'] = True
    with app.app_context():
        from models import db
        db.create_all()

    r = client.get(
        '/start?utm_source=google&utm_medium=cpc&utm_campaign=test&gclid=abc123',
        base_url=PUBLIC,
    )
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'اطلب تجربة' in body
    assert 'name="next" value="/start"' in body
    assert 'utm_source' in body

    r = client.post(
        '/demo-request',
        data={
            'company_name': 'شركة إعلان',
            'contact_name': 'سارة',
            'contact_email': 'ads-buyer@example.com',
            'phone': '0566299626',
            'city': 'مكة المكرمة',
            'elevators': '8',
            'request_type': 'demo',
            'next': '/start',
            'utm_source': 'google',
            'utm_medium': 'cpc',
            'utm_campaign': 'test',
            'gclid': 'abc123',
        },
        base_url=PUBLIC,
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert '/start/thanks' in (r.headers.get('Location') or '')

    with app.app_context():
        from models import SalesLead
        lead = SalesLead.query.filter_by(contact_email='ads-buyer@example.com').order_by(SalesLead.id.desc()).first()
        assert lead is not None
        assert lead.source_path == '/start'
        assert lead.utm_source == 'google'
        assert lead.utm_campaign == 'test'
        assert lead.gclid == 'abc123'

    r = client.get('/start/thanks', base_url=PUBLIC)
    assert r.status_code == 200
    assert 'وصل طلبك' in r.get_data(as_text=True)


def test_product_path_public():
    client = app.test_client()
    app.config['TESTING'] = True
    r = client.get('/product', base_url=PUBLIC, follow_redirects=False)
    assert r.status_code == 200
    assert 'صيانة المصاعد' in r.get_data(as_text=True)


def test_pricing_not_forced_login_on_public_host():
    client = app.test_client()
    app.config['TESTING'] = True
    r = client.get('/pricing', base_url=PUBLIC, follow_redirects=False)
    assert r.status_code == 200
    # يجب ألا يحوّل للدخول
    assert r.status_code != 302 or '/login' not in (r.headers.get('Location') or '')


def test_marketing_context_matches_catalog():
    from marketing_site import build_pricing_addons, build_pricing_plans
    from plan_catalog import ADDON_CATALOG, PLAN_CATALOG, PLAN_ORDER

    plans = build_pricing_plans()
    assert [p['key'] for p in plans] == list(PLAN_ORDER)
    assert plans[0]['yearly_sar'] == PLAN_CATALOG['basic']['yearly_sar']
    assert any(p['featured'] for p in plans)

    addons = build_pricing_addons()
    assert len(addons) == len(ADDON_CATALOG)
    assert {a['key'] for a in addons} == set(ADDON_CATALOG)
