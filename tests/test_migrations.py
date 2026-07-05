"""G6 — Alembic migrations: ترقية قاعدة جديدة + stamp لقاعدة موجودة."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_script(script_rel: str, env: dict) -> subprocess.CompletedProcess[str]:
    full_env = os.environ.copy()
    full_env.update(env)
    full_env.setdefault('SECRET_KEY', 'test-migrate-secret')
    return subprocess.run(
        [sys.executable, os.path.join(ROOT, script_rel)],
        cwd=ROOT,
        env=full_env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


def _table_names(db_path: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def test_alembic_upgrade_fresh_database(tmp_path):
    db_file = tmp_path / 'fresh.db'
    uri = 'sqlite:///' + db_file.as_posix()
    result = _run_script('deploy/migrate_db.py', {
        'DATABASE_URL': uri,
        'LIFTCORE_ALEMBIC': '1',
    })
    assert result.returncode == 0, result.stdout

    tables = _table_names(str(db_file))
    assert 'alembic_version' in tables
    assert 'users' in tables
    assert 'customers' in tables
    assert 'installation_projects' in tables


def test_alembic_upgrade_idempotent(tmp_path):
    db_file = tmp_path / 'idem.db'
    uri = 'sqlite:///' + db_file.as_posix()
    env = {'DATABASE_URL': uri, 'LIFTCORE_ALEMBIC': '1'}
    first = _run_script('deploy/migrate_db.py', env)
    second = _run_script('deploy/migrate_db.py', env)
    assert first.returncode == 0, first.stdout
    assert second.returncode == 0, second.stdout


def test_alembic_stamps_legacy_database(tmp_path):
    """قاعدة أنشأها create_all بدون alembic_version → stamp فقط."""
    db_file = tmp_path / 'legacy.db'
    uri = 'sqlite:///' + db_file.as_posix()
    bootstrap = _run_script('scripts/bootstrap_legacy_db.py', {
        'DATABASE_URL': uri,
        'LIFTCORE_ALEMBIC': '0',
    })
    assert bootstrap.returncode == 0, bootstrap.stdout

    before = _table_names(str(db_file))
    assert 'users' in before
    assert 'alembic_version' not in before

    migrated = _run_script('deploy/migrate_db.py', {
        'DATABASE_URL': uri,
        'LIFTCORE_ALEMBIC': '1',
    })
    assert migrated.returncode == 0, migrated.stdout
    assert 'stamping' in migrated.stdout.lower()

    after = _table_names(str(db_file))
    assert 'alembic_version' in after
    assert 'users' in after
