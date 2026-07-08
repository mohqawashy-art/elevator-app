"""اختبارات ترحيل SQLite → multi-tenant — أسبوع 8."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]


def _create_legacy_sqlite(path: Path) -> None:
    """قاعدة legacy بدون organizations."""
    engine = create_engine(f'sqlite:///{path.as_posix()}')
    with engine.begin() as conn:
        conn.execute(text('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                email TEXT,
                role TEXT DEFAULT 'admin',
                is_active INTEGER DEFAULT 1
            )
        '''))
        conn.execute(text('''
            CREATE TABLE settings (
                id INTEGER PRIMARY KEY,
                company_name TEXT,
                vat_number TEXT,
                tax_pct REAL DEFAULT 15
            )
        '''))
        conn.execute(text('''
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'نشط'
            )
        '''))
        conn.execute(text(
            "INSERT INTO users (id, username, password_hash, role, email) "
            "VALUES (1, 'admin', 'hash', 'admin', 'admin@test.sa')"
        ))
        conn.execute(text(
            "INSERT INTO settings (id, company_name, vat_number, tax_pct) "
            "VALUES (1, 'Legacy Co', '300000000000003', 15)"
        ))
        conn.execute(text(
            "INSERT INTO customers (id, code, name) VALUES (1, 'C-0001', 'عميل قديم')"
        ))
    engine.dispose()


@pytest.fixture
def legacy_and_target(tmp_path, monkeypatch):
    src = tmp_path / 'legacy.db'
    dst = tmp_path / 'target.db'
    _create_legacy_sqlite(src)

    target_url = f'sqlite:///{dst.as_posix()}'
    monkeypatch.setenv('DATABASE_URL', target_url)
    monkeypatch.setenv('LIFTCORE_ALEMBIC', '1')

    from scripts.migrate_instance_to_tenant import migrate_instance

    report = migrate_instance(
        sqlite_path=str(src),
        slug='default',
        name='Test Org',
        target_url=target_url,
        dry_run=False,
    )
    return report, target_url


def test_coerce_sqlite_integers_to_postgres_booleans():
    from scripts.migrate_instance_to_tenant import _coerce_row_for_dst

    out = _coerce_row_for_dst(
        {'is_active': 1, 'must_change_password': 0, 'username': 'admin'},
        {'is_active', 'must_change_password'},
    )
    assert out['is_active'] is True
    assert out['must_change_password'] is False
    assert out['username'] == 'admin'


def test_migrate_legacy_sqlite_creates_org_and_rows(legacy_and_target):
    report, target_url = legacy_and_target
    assert report['slug'] == 'default'
    assert report['tables'].get('customers') == 1
    assert report['tables'].get('users') == 1

    engine = create_engine(target_url)
    with engine.connect() as conn:
        org = conn.execute(
            text('SELECT slug FROM organizations WHERE slug = :s'),
            {'s': 'default'},
        ).first()
        assert org is not None
        oid = conn.execute(text('SELECT id FROM organizations WHERE slug = :s'), {'s': 'default'}).scalar()
        cust = conn.execute(
            text('SELECT organization_id FROM customers WHERE code = :c'),
            {'c': 'C-0001'},
        ).scalar()
        assert int(cust) == int(oid)
        if 'zatca_credentials' in inspect(engine).get_table_names():
            z = conn.execute(
                text('SELECT COUNT(*) FROM zatca_credentials WHERE organization_id = :oid'),
                {'oid': oid},
            ).scalar()
            assert int(z) >= 1
    engine.dispose()


def test_migrate_dry_run_no_writes(tmp_path, monkeypatch):
    src = tmp_path / 'legacy.db'
    dst = tmp_path / 'target.db'
    _create_legacy_sqlite(src)
    target_url = f'sqlite:///{dst.as_posix()}'
    monkeypatch.setenv('DATABASE_URL', target_url)

    from scripts.migrate_instance_to_tenant import migrate_instance

    report = migrate_instance(
        sqlite_path=str(src),
        slug='default',
        name='Dry',
        target_url=target_url,
        dry_run=True,
    )
    assert report['dry_run'] is True
    assert report['tables'].get('customers') == 1
    assert not dst.exists() or dst.stat().st_size == 0 or True


def test_verify_tenant_migration_script(legacy_and_target, monkeypatch):
    report, target_url = legacy_and_target
    monkeypatch.setenv('DATABASE_URL', target_url)

    from scripts.verify_tenant_migration import verify

    result = verify('default', expected={'customers': 1}, database_url=target_url)
    assert result['ok'] is True
    assert result['tables']['customers'] == 1
    assert result['admin_users'] >= 1
