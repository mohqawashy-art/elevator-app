"""P2 K1 — smoke بوابة الفني."""
from __future__ import annotations


def test_field_login_page_loads(client):
    r = client.get('/field/login')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'field' in html.lower() or 'فني' in html or 'PIN' in html


def test_field_home_redirects_without_session(client):
    r = client.get('/field', follow_redirects=False)
    assert r.status_code in (302, 401, 403)


def test_field_api_me_requires_auth(client):
    r = client.get('/api/field/me')
    assert r.status_code in (401, 403)
