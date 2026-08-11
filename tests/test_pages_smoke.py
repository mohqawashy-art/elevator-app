"""Smoke — الصفحات الرئيسية تُحمّل بدون 500 + عناصر UI أساسية (P0-D3)."""
from tests.conftest import login_as

MAIN_PAGES = (
    '/dashboard',
    '/clients',
    '/invoices',
    '/contracts',
    '/reports',
    '/reports/parts-billing',
    '/maintenance-visits',
    '/elevators',
    '/settings',
)

REQUIRED_FRAGMENTS = (
    'id="h-date"',
    'liftcore-csrf.js',
    'liftcore-shell.js',
    '__LC_CAN_WRITE',
)


def test_main_pages_load_for_admin(client):
    login_as(client, 'admin')
    for path in MAIN_PAGES:
        # /contracts يعيد توجيهاً إلى ?z=4 لكسر كاش الواجهة القديمة
        r = client.get(path, follow_redirects=True)
        assert r.status_code == 200, f'{path} returned {r.status_code}'
        html = r.get_data(as_text=True)
        for frag in REQUIRED_FRAGMENTS:
            assert frag in html, f'{path} missing {frag}'


def test_main_pages_no_obvious_script_typos(client):
    login_as(client, 'admin')
    for path in MAIN_PAGES:
        html = client.get(path, follow_redirects=True).get_data(as_text=True)
        assert 'undefined is not' not in html
        assert 'null is not an object' not in html


def test_viewer_can_read_dashboard(client):
    login_as(client, 'viewer')
    r = client.get('/dashboard')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert '__LC_IS_VIEWER' in html or '__LC_CAN_WRITE": false' in html.replace(' ', '')
