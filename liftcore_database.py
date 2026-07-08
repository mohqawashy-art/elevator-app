"""LiftCore — إعداد قاعدة البيانات (SQLite محلي / PostgreSQL إنتاج)."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse, urlunparse


def normalize_database_url(url: str | None) -> str:
    """توحيد رابط SQLAlchemy — postgres:// → postgresql+psycopg:// (psycopg v3)."""
    raw = (url or '').strip()
    if not raw:
        return raw
    if raw.startswith('postgres://'):
        raw = 'postgresql://' + raw[len('postgres://') :]
    # SQLAlchemy يختار psycopg2 افتراضياً لـ postgresql:// — نثبت psycopg v3 في requirements
    if raw.startswith('postgresql://'):
        return 'postgresql+psycopg://' + raw[len('postgresql://') :]
    return raw


def database_backend(url: str | None = None) -> str:
    """sqlite | postgresql | other."""
    raw = normalize_database_url(url or os.environ.get('DATABASE_URL') or '')
    if not raw:
        return 'sqlite'
    scheme = urlparse(raw).scheme.lower()
    if scheme in ('sqlite', 'sqlite+pysqlite'):
        return 'sqlite'
    if scheme in ('postgresql', 'postgresql+psycopg', 'postgresql+psycopg2'):
        return 'postgresql'
    return scheme or 'unknown'


def is_postgresql(url: str | None = None) -> bool:
    return database_backend(url) == 'postgresql'


def is_sqlite(url: str | None = None) -> bool:
    return database_backend(url) in ('sqlite', '')


def apply_database_config(app) -> None:
    """تطبيق URI وخيارات المحرك حسب نوع القاعدة."""
    uri = normalize_database_url(app.config.get('SQLALCHEMY_DATABASE_URI'))
    app.config['SQLALCHEMY_DATABASE_URI'] = uri
    if is_postgresql(uri):
        opts = dict(app.config.get('SQLALCHEMY_ENGINE_OPTIONS') or {})
        opts.setdefault('pool_pre_ping', True)
        opts.setdefault('pool_recycle', 280)
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = opts


def database_info(app) -> dict[str, Any]:
    """معلومات القاعدة للتشخيص — بدون كشف كلمات المرور."""
    uri = normalize_database_url(app.config.get('SQLALCHEMY_DATABASE_URI', ''))
    backend = database_backend(uri)
    info: dict[str, Any] = {'backend': backend}
    if backend == 'sqlite' and uri.startswith('sqlite:///'):
        info['path'] = uri.replace('sqlite:///', '', 1)
    elif backend == 'postgresql':
        parsed = urlparse(uri)
        info['host'] = parsed.hostname or ''
        info['database'] = (parsed.path or '').lstrip('/')
    return info


def reset_postgres_sequences(connection, table_names: list[str]) -> None:
    """ضبط تسلسلات PostgreSQL بعد استيراد بيانات."""
    import re

    from sqlalchemy import text

    for table in table_names:
        if not re.fullmatch(r'[a-z_][a-z0-9_]*', table):
            continue
        connection.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"GREATEST(COALESCE((SELECT MAX(id) FROM {table}), 1), 1))"
            )
        )
