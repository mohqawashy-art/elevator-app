"""P0-D3 — الصفحات الرئيسية بدون أخطاء JS واضحة في HTML."""
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

BAD_FRAGMENTS = (
    'undefined is not',
    'null is not an object',
    'SyntaxError',
    'ReferenceError',
    'is not defined',
)


def test_main_pages_no_obvious_js_errors(client):
    login_as(client, 'admin')
    for path in MAIN_PAGES:
        html = client.get(path).get_data(as_text=True)
        assert html, f'{path} returned empty body'
        for bad in BAD_FRAGMENTS:
            assert bad not in html, f'{path} contains JS error fragment: {bad}'
