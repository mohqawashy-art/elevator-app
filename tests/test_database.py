"""F7 — إعداد قاعدة البيانات و PostgreSQL."""
import os
import sys

import pytest
from flask import Flask

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from liftcore_database import (
    apply_database_config,
    database_backend,
    database_info,
    is_postgresql,
    is_sqlite,
    normalize_database_url,
)


def test_normalize_postgres_url():
    assert normalize_database_url('postgres://u:p@localhost/db') == (
        'postgresql://u:p@localhost/db'
    )
    assert normalize_database_url('postgresql://localhost/x') == 'postgresql://localhost/x'


def test_database_backend_detection():
    assert database_backend('sqlite:///instance/x.db') == 'sqlite'
    assert database_backend('postgresql://localhost/liftcore') == 'postgresql'
    assert is_sqlite('sqlite:///:memory:')
    assert is_postgresql('postgresql://user:pass@db/liftcore')


def test_apply_database_config_postgres_engine_options():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/liftcore'
    apply_database_config(app)
    opts = app.config.get('SQLALCHEMY_ENGINE_OPTIONS') or {}
    assert opts.get('pool_pre_ping') is True
    assert opts.get('pool_recycle') == 280


def test_database_info_masks_password():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:secret@db.example.com:5432/liftcore'
    apply_database_config(app)
    info = database_info(app)
    assert info['backend'] == 'postgresql'
    assert info['host'] == 'db.example.com'
    assert info['database'] == 'liftcore'
    assert 'secret' not in str(info)


def test_health_reports_database_backend(client):
    r = client.get('/api/health')
    assert r.status_code in (200, 503)
    data = r.get_json()
    assert data.get('database_backend') == 'sqlite'
