"""إعدادات PWA تطبيق الإدارة — جوال وتابلت."""
from __future__ import annotations


def test_admin_manifest_branding(client):
    r = client.get('/manifest.webmanifest')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'LiftCore' in body
    assert '/dashboard' in body
    assert 'JAMA' not in body


def test_admin_service_worker_route(client):
    r = client.get('/sw.js')
    assert r.status_code == 200
    assert 'liftcore-admin' in r.get_data(as_text=True)
    assert r.headers.get('Service-Worker-Allowed') == '/'


def test_admin_mobile_css_exists():
    from pathlib import Path

    css = Path(__file__).resolve().parents[1] / 'static' / 'liftcore-admin-mobile.css'
    assert css.is_file()
    text = css.read_text(encoding='utf-8')
    assert '1100px' in text
    assert 'hamburger' in text
    assert 'pointer-events: none' in text


def test_mobile_scroll_layout_overrides():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / 'static'
    layout = (root / 'liftcore-layout.css').read_text(encoding='utf-8')
    touch_js = (root / 'liftcore-mobile-touch.js').read_text(encoding='utf-8')
    touch_css = (root / 'liftcore-mobile-touch.css').read_text(encoding='utf-8')
    assert 'lc-mobile-native' in layout
    assert 'overflow-y: auto !important' in layout
    assert 'LiftCoreMobileTouch' in touch_js
    assert 'lc-mobile-native' in touch_css
