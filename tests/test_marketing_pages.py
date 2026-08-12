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

    r = client.get('/pricing', base_url=PUBLIC)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'Basic' in body
    assert 'Plus' in body
    assert '3,000' in body or '3000' in body
    assert 'ر.س' in body
    assert 'login' not in (r.headers.get('Location') or '').lower()


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
