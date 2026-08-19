"""عزل ملف البيئة بين staging والإنتاج."""
from __future__ import annotations

import os

import app as app_module
import liftcore_mail
import moyasar_payments


def test_configured_env_file_overrides_without_platform_fallback(tmp_path, monkeypatch):
    env_file = tmp_path / 'staging.env'
    env_file.write_text(
        'LIFTCORE_ENV=staging\n'
        'DATABASE_URL=sqlite:///staging-only.db\n'
        'MAIL_API_KEY=staging-mail\n',
        encoding='utf-8',
    )
    monkeypatch.setenv('LIFTCORE_ENV_FILE', str(env_file))
    monkeypatch.setenv('DATABASE_URL', 'production-sentinel')
    monkeypatch.delenv('LIFTCORE_ENV', raising=False)
    monkeypatch.delenv('MAIL_API_KEY', raising=False)

    app_module._load_env_file()

    assert os.environ['LIFTCORE_ENV'] == 'staging'
    assert os.environ['DATABASE_URL'] == 'sqlite:///staging-only.db'
    assert os.environ['MAIL_API_KEY'] == 'staging-mail'


def test_mail_and_moyasar_refresh_from_configured_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / 'staging.env'
    env_file.write_text(
        'MAIL_API_KEY=isolated-mail\n'
        'MAIL_FROM=staging@example.test\n'
        'MOYASAR_SECRET_KEY=isolated-payment\n'
        'MOYASAR_PUBLISHABLE_KEY=isolated-publishable\n',
        encoding='utf-8',
    )
    monkeypatch.setenv('LIFTCORE_ENV_FILE', str(env_file))
    monkeypatch.delenv('MAIL_API_KEY', raising=False)
    monkeypatch.delenv('MAIL_FROM', raising=False)
    monkeypatch.delenv('MOYASAR_SECRET_KEY', raising=False)
    monkeypatch.delenv('MOYASAR_PUBLISHABLE_KEY', raising=False)

    liftcore_mail._ensure_mail_env()
    moyasar_payments._ensure_moyasar_env()

    assert os.environ['MAIL_API_KEY'] == 'isolated-mail'
    assert os.environ['MAIL_FROM'] == 'staging@example.test'
    assert os.environ['MOYASAR_SECRET_KEY'] == 'isolated-payment'
    assert os.environ['MOYASAR_PUBLISHABLE_KEY'] == 'isolated-publishable'
