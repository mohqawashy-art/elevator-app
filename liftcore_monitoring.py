"""LiftCore — مراقبة الأخطاء (Sentry اختياري عبر SENTRY_DSN)."""

from __future__ import annotations

import os
from typing import Any

_SENSITIVE_HEADERS = frozenset({
    'cookie',
    'authorization',
    'x-csrf-token',
    'x-api-key',
})


def _scrub_event(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    request = event.get('request')
    if isinstance(request, dict):
        headers = request.get('headers')
        if isinstance(headers, dict):
            for key in list(headers):
                if key.lower() in _SENSITIVE_HEADERS:
                    headers[key] = '[Filtered]'
    user = event.get('user')
    if isinstance(user, dict):
        user.pop('ip_address', None)
    return event


def init_error_monitoring(app) -> bool:
    """تهيئة Sentry عند توفر DSN — لا تفشل التشغيل إن غاب."""
    dsn = (os.environ.get('SENTRY_DSN') or '').strip()
    if not dsn:
        app.logger.info('Sentry: SENTRY_DSN not set — skipped')
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        app.logger.warning(
            'Sentry: sentry-sdk not installed — pip install "sentry-sdk[flask]"'
        )
        return False

    environment = (
        os.environ.get('SENTRY_ENVIRONMENT')
        or os.environ.get('LIFTCORE_TENANT')
        or ('production' if os.environ.get('LIFTCORE_HTTPS', '').strip().lower() in ('1', 'true', 'yes') else 'development')
    )
    release = (os.environ.get('SENTRY_RELEASE') or os.environ.get('LIFTCORE_VERSION') or '').strip() or None
    try:
        traces = float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0') or '0')
    except ValueError:
        traces = 0.0
    traces = max(0.0, min(1.0, traces))

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            FlaskIntegration(),
            SqlalchemyIntegration(),
        ],
        environment=environment,
        release=release,
        traces_sample_rate=traces,
        send_default_pii=False,
        before_send=_scrub_event,
    )
    app.logger.info('Sentry: enabled (environment=%s)', environment)
    return True


def monitoring_status() -> dict[str, Any]:
    dsn = (os.environ.get('SENTRY_DSN') or '').strip()
    env = (
        os.environ.get('SENTRY_ENVIRONMENT')
        or os.environ.get('LIFTCORE_TENANT')
        or ''
    )
    return {
        'sentry_configured': bool(dsn),
        'environment': env,
    }
