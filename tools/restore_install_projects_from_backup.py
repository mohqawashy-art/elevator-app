#!/usr/bin/env python3
"""استعادة مشاريع تركيب من نسخة pg_dump (بأكواد PRJ-XXXX)."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from flask import g
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app import app  # noqa: E402
from liftcore_database import is_postgresql, normalize_database_url  # noqa: E402
from models import Organization  # noqa: E402

RELATED_TABLES = (
    'installation_projects',
    'installation_quotations',
    'installation_quotation_lines',
    'installation_timeline_steps',
    'installation_project_costs',
    'installation_project_receipts',
)


def parse_pg_uri(uri: str) -> dict:
    parsed = urlparse(normalize_database_url(uri))
    return {
        'host': parsed.hostname or 'localhost',
        'port': str(parsed.port or 5432),
        'user': parsed.username or 'postgres',
        'password': parsed.password or '',
        'dbname': (parsed.path or '/liftcore').lstrip('/'),
    }


def temp_db_name(main: str) -> str:
    base = f'{main}_restore_snap'
    return base[:63]


def _pg_env(pg: dict) -> dict:
    env = os.environ.copy()
    if pg['password']:
        env['PGPASSWORD'] = pg['password']
    return env


def run_pg(cmd: list[str], env: dict) -> None:
    subprocess.run(cmd, check=True, env=env)


def run_pg_admin(cmd: list[str], env: dict) -> None:
    """createdb/dropdb كمستخدم postgres محلياً (بدون طلب كلمة مرور)."""
    base = cmd[0]
    if base in ('createdb', 'dropdb'):
        args = cmd[1:]
        # أزل -h/-p/-U لاستخدام peer auth مع postgres
        cleaned = []
        skip_next = False
        for i, a in enumerate(args):
            if skip_next:
                skip_next = False
                continue
            if a in ('-h', '-p', '-U'):
                skip_next = True
                continue
            cleaned.append(a)
        run_pg(['sudo', '-u', 'postgres', base, *cleaned], env)
        return
    try:
        run_pg(cmd, env)
    except subprocess.CalledProcessError:
        run_pg(['sudo', '-u', 'postgres', *cmd], env)


def ensure_temp_db(pg: dict, temp_name: str, backup: Path) -> None:
    env = _pg_env(pg)
    run_pg_admin(['dropdb', '--if-exists', temp_name], env)
    run_pg_admin(['createdb', '-O', pg['user'], temp_name], env)
    run_pg([
        'pg_restore', '-h', pg['host'], '-p', pg['port'], '-U', pg['user'],
        '-d', temp_name, '--no-owner', '--role', pg['user'], str(backup),
    ], env)


def project_ids_for_codes(engine, org_id: int, codes: list[str]) -> list[int]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                'SELECT id, code FROM installation_projects '
                'WHERE organization_id = :oid AND code = ANY(:codes) ORDER BY id'
            ),
            {'oid': org_id, 'codes': codes},
        ).fetchall()
    return [int(r[0]) for r in rows]


def copy_table_rows(src_engine, dst_engine, table: str, where_sql: str, params: dict) -> int:
    insp = inspect(src_engine)
    if table not in insp.get_table_names():
        return 0
    cols = [c['name'] for c in insp.get_columns(table)]
    col_list = ', '.join(cols)
    sel = f'SELECT {col_list} FROM {table} WHERE {where_sql}'
    with src_engine.connect() as src:
        rows = src.execute(text(sel), params).mappings().all()
    if not rows:
        return 0
    placeholders = ', '.join(f':{c}' for c in cols)
    insert_sql = f'INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
    count = 0
    with dst_engine.begin() as dst:
        for row in rows:
            res = dst.execute(text(insert_sql), dict(row))
            count += res.rowcount or 0
    return count


def restore_codes(backup: Path, org_slug: str, codes: list[str], dry_run: bool) -> None:
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not is_postgresql(uri):
        raise SystemExit('PostgreSQL only')
    pg = parse_pg_uri(uri)
    temp_name = temp_db_name(pg['dbname'])
    temp_uri = uri.replace(f'/{pg["dbname"]}', f'/{temp_name}')

    with app.app_context():
        org = Organization.query.filter_by(slug=org_slug).one()
        g.organization = org
        g.organization_id = org.id
        org_id = org.id

    print(f'backup={backup}')
    print(f'org={org_slug} id={org_id} codes={codes}')
    if dry_run:
        ensure_temp_db(pg, temp_name, backup)
        src = create_engine(temp_uri)
        ids = project_ids_for_codes(src, org_id, codes)
        for pid in ids:
            with src.connect() as conn:
                row = conn.execute(
                    text('SELECT code, status, title FROM installation_projects WHERE id=:id'),
                    {'id': pid},
                ).one()
            print(f'WOULD_RESTORE id={pid} code={row[0]} status={row[1]} title={row[2] or ""}')
        run_pg_admin(['dropdb', '--if-exists', temp_name], _pg_env(pg))
        return

    ensure_temp_db(pg, temp_name, backup)
    src_engine = create_engine(temp_uri)
    dst_engine = create_engine(uri)
    project_ids = project_ids_for_codes(src_engine, org_id, codes)
    if not project_ids:
        print('NO_PROJECTS_IN_BACKUP')
    else:
        pid_list = project_ids
        copy_table_rows(
            src_engine, dst_engine, 'installation_projects',
            'organization_id = :oid AND id = ANY(:ids)',
            {'oid': org_id, 'ids': pid_list},
        )
        q_ids = []
        with src_engine.connect() as conn:
            q_ids = [
                int(r[0]) for r in conn.execute(
                    text('SELECT id FROM installation_quotations WHERE project_id = ANY(:pids)'),
                    {'pids': pid_list},
                ).fetchall()
            ]
        if q_ids:
            copy_table_rows(
                src_engine, dst_engine, 'installation_quotations',
                'id = ANY(:ids)',
                {'ids': q_ids},
            )
            copy_table_rows(
                src_engine, dst_engine, 'installation_quotation_lines',
                'quotation_id = ANY(:ids)',
                {'ids': q_ids},
            )
        copy_table_rows(
            src_engine, dst_engine, 'installation_timeline_steps',
            'project_id = ANY(:pids)',
            {'pids': pid_list},
        )
        copy_table_rows(
            src_engine, dst_engine, 'installation_project_costs',
            'project_id = ANY(:pids)',
            {'pids': pid_list},
        )
        copy_table_rows(
            src_engine, dst_engine, 'installation_project_receipts',
            'project_id = ANY(:pids)',
            {'pids': pid_list},
        )
        for pid in pid_list:
            with dst_engine.connect() as conn:
                row = conn.execute(
                    text('SELECT code FROM installation_projects WHERE id=:id'),
                    {'id': pid},
                ).first()
            print(f'RESTORED {pid} {row[0] if row else "?"}')

    run_pg_admin(['dropdb', '--if-exists', temp_name], _pg_env(pg))


def expand_code_range(spec: str) -> list[str]:
    if '-' not in spec:
        raise ValueError(spec)
    start, end = spec.split('-', 1)
    lo, hi = int(start), int(end)
    return [f'PRJ-{n:04d}' for n in range(lo, hi + 1)]


def main() -> None:
    parser = argparse.ArgumentParser(description='Restore installation projects from pg_dump by PRJ code')
    parser.add_argument('--backup', required=True, type=Path)
    parser.add_argument('--org', default='jama')
    parser.add_argument('--codes', nargs='+', default=[])
    parser.add_argument('--code-range', help='e.g. 5-11 → PRJ-0005..PRJ-0011')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    codes = list(args.codes)
    if args.code_range:
        codes.extend(expand_code_range(args.code_range))
    if not codes:
        raise SystemExit('Provide --codes or --code-range')
    restore_codes(args.backup, args.org, codes, args.dry_run)


if __name__ == '__main__':
    main()
