#!/usr/bin/env python3
"""نسخ احتياطي — SQLite (ملف) أو PostgreSQL (pg_dump)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from liftcore_database import database_backend, is_postgresql, is_sqlite, normalize_database_url  # noqa: E402


def _resolve_sqlite_path() -> Path | None:
    from app import app

    with app.app_context():
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if is_sqlite(uri) and uri.startswith('sqlite:///'):
        raw = uri.replace('sqlite:///', '', 1)
        return Path(raw)
    for candidate in (ROOT / 'instance' / 'liftcore.db', ROOT / 'liftcore.db'):
        if candidate.is_file():
            return candidate
    return None


def backup_sqlite(dest: Path) -> Path:
    src = _resolve_sqlite_path()
    if not src or not src.is_file():
        raise FileNotFoundError('SQLite database file not found')
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def backup_postgres(dest: Path) -> Path:
    uri = normalize_database_url(os.environ.get('DATABASE_URL', ''))
    if not is_postgresql(uri):
        raise RuntimeError('DATABASE_URL is not PostgreSQL')
    parsed = urlparse(uri)
    env = os.environ.copy()
    if parsed.password:
        env['PGPASSWORD'] = parsed.password
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        'pg_dump',
        '-h', parsed.hostname or 'localhost',
        '-p', str(parsed.port or 5432),
        '-U', parsed.username or 'postgres',
        '-d', (parsed.path or '/liftcore').lstrip('/'),
        '-Fc',
        '-f', str(dest),
    ]
    subprocess.run(cmd, check=True, env=env)
    return dest


def main() -> int:
    out_dir = Path(os.environ.get('BACKUP_ROOT', ROOT / 'backups'))
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    backend = database_backend(os.environ.get('DATABASE_URL'))
    if backend == 'postgresql':
        target = out_dir / f'liftcore-{ts}.dump'
        path = backup_postgres(target)
        print(f'OK PostgreSQL backup: {path}')
    else:
        target = out_dir / f'liftcore-{ts}.db'
        path = backup_sqlite(target)
        print(f'OK SQLite backup: {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
