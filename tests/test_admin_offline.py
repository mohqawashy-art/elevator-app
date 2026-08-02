"""Admin Offline PWA — assets, SW routes, queue API."""
from __future__ import annotations

from pathlib import Path

from tests.conftest import login_as

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'static'


def test_admin_offline_assets_exist():
    for name in (
        'admin-offline.js',
        'admin-sw.js',
        'admin-offline-fallback.html',
    ):
        assert (STATIC / name).is_file(), f'missing static/{name}'


def test_admin_offline_js_has_queue_api():
    text = (STATIC / 'admin-offline.js').read_text(encoding='utf-8')
    assert 'LiftCoreAdminOffline' in text
    assert 'flushQueue' in text
    assert 'enqueueForm' in text
    assert 'enqueueJson' in text
    assert 'patchFetch' in text
    assert 'queueFetchRequest' in text
    assert 'indexedDB' in text
    assert 'lc-admin-offline-banner' in text


def test_admin_sw_caches_nav_and_fallback():
    text = (STATIC / 'admin-sw.js').read_text(encoding='utf-8')
    assert 'liftcore-admin-v7' in text
    assert '/dashboard' in text
    assert 'admin-offline-fallback.html' in text
    assert 'admin-offline.js' in text


def test_admin_service_worker_serves_offline_bundle(client):
    r = client.get('/sw.js')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'liftcore-admin' in body
    assert 'admin-offline' in body or '/dashboard' in body
    assert r.headers.get('Service-Worker-Allowed') == '/'


def test_admin_offline_fallback_route(client):
    r = client.get('/static/admin-offline-fallback.html')
    assert r.status_code == 200
    assert 'لا يوجد اتصال' in r.get_data(as_text=True)


def test_dashboard_includes_admin_offline_script(client):
    login_as(client, 'admin')
    r = client.get('/dashboard')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'admin-offline.js' in html


def test_clients_includes_admin_offline_script(client):
    login_as(client, 'admin')
    r = client.get('/clients')
    assert r.status_code == 200
    assert 'admin-offline.js' in r.get_data(as_text=True)
