"""F5 — مراقبة الأخطاء (Sentry)."""
import os
import sys

import pytest
from flask import Flask

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from liftcore_monitoring import init_error_monitoring, monitoring_status


def test_monitoring_status_without_dsn(monkeypatch):
    monkeypatch.delenv('SENTRY_DSN', raising=False)
    monkeypatch.delenv('SENTRY_ENVIRONMENT', raising=False)
    status = monitoring_status()
    assert status['sentry_configured'] is False
    assert status['environment'] == ''


def test_monitoring_status_with_dsn(monkeypatch):
    monkeypatch.setenv('SENTRY_DSN', 'https://key@o0.ingest.sentry.io/1')
    monkeypatch.setenv('SENTRY_ENVIRONMENT', 'staging')
    status = monitoring_status()
    assert status['sentry_configured'] is True
    assert status['environment'] == 'staging'


def test_init_skips_without_dsn(monkeypatch):
    monkeypatch.delenv('SENTRY_DSN', raising=False)
    app = Flask(__name__)
    assert init_error_monitoring(app) is False


def test_init_enables_with_dsn(monkeypatch):
    sentry_sdk = pytest.importorskip('sentry_sdk')
    captured: list[dict] = []

    def _fake_init(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(sentry_sdk, 'init', _fake_init)
    monkeypatch.setenv('SENTRY_DSN', 'https://key@o0.ingest.sentry.io/1')
    monkeypatch.setenv('SENTRY_ENVIRONMENT', 'test')
    monkeypatch.setenv('LIFTCORE_HTTPS', '0')
    app = Flask(__name__)
    assert init_error_monitoring(app) is True
    assert captured
    assert captured[0]['dsn'].startswith('https://')


def test_health_includes_monitoring(client, monkeypatch):
    monkeypatch.delenv('SENTRY_DSN', raising=False)
    r = client.get('/api/health')
    assert r.status_code in (200, 503)
    data = r.get_json()
    assert 'monitoring' in data
    assert data['monitoring']['sentry_configured'] is False
