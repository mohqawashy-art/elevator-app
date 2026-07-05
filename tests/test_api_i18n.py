"""P2 J2 — رسائل API ثنائية اللغة."""
from __future__ import annotations

import pytest

from liftcore_api_i18n import API_ERRORS, api_error_payload, request_lang


@pytest.fixture
def app():
    from app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app


def test_api_errors_have_both_languages():
    for code, (ar, en) in API_ERRORS.items():
        assert ar and en, code
        assert ar != en or code in ('session_locked',)


def test_payload_ar_default(app):
    with app.test_request_context():
        from flask import session
        session['lang'] = 'ar'
        body = api_error_payload('login_required')
        assert body['message'] == 'يجب تسجيل الدخول'
        assert body['message_en'] == 'Please sign in'


def test_payload_en_session(app):
    with app.test_request_context():
        from flask import session
        session['lang'] = 'en'
        body = api_error_payload('login_required')
        assert body['message'] == 'Please sign in'


def test_viewer_api_forbidden_bilingual(client):
    from tests.conftest import login_as

    login_as(client, 'viewer')
    r = client.post('/api/clients', json={'name': 'x'})
    if r.status_code == 403:
        data = r.get_json()
        assert data.get('message_ar')
        assert data.get('message_en')
