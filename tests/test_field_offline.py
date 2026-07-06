"""P3 — Offline Field PWA assets and routes."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'static'


def test_field_offline_assets_exist():
    for name in (
        'field-offline.js',
        'field-sw.js',
        'field-manifest.webmanifest',
    ):
        assert (STATIC / name).is_file(), f'missing static/{name}'


def test_field_manifest_route(client):
    r = client.get('/field/manifest.webmanifest')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'field/login' in body
    assert 'LiftCore' in body


def test_field_service_worker_route(client):
    r = client.get('/field/sw.js')
    assert r.status_code == 200
    assert 'liftcore-field' in r.get_data(as_text=True)
    assert r.headers.get('Service-Worker-Allowed') == '/field/'


def test_field_home_includes_offline_scripts(client):
    r = client.get('/field', follow_redirects=False)
    assert r.status_code in (302, 401, 403)
    r2 = client.get('/field/login')
    assert r2.status_code == 200
    html = r2.get_data(as_text=True)
    assert 'manifest.webmanifest' in html or 'field/manifest' in html


def test_field_offline_js_has_queue_api():
    text = (STATIC / 'field-offline.js').read_text(encoding='utf-8')
    assert 'flushQueue' in text
    assert 'postJson' in text
    assert 'indexedDB' in text
