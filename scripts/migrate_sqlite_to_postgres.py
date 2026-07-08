#!/usr/bin/env python3
"""ترحيل بيانات SQLite → PostgreSQL (F7).

المتطلبات:
  - قاعدة PostgreSQL فارغة + DATABASE_URL
  - ملف SQLite المصدر عبر SQLITE_SOURCE

  export DATABASE_URL=postgresql://liftcore:secret@localhost/liftcore
  export SQLITE_SOURCE=/path/to/instance/liftcore.db
  python scripts/migrate_sqlite_to_postgres.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# ترتيب الإدراج — يتجاوز دورات FK قدر الإمكان
COPY_ORDER = [
    'users',
    'settings',
    'customers',
    'technicians',
    'technician_documents',
    'maintenance_teams',
    'signatories',
    'inventory_items',
    'elevators',
    'contracts',
    'contract_elevators',
    'maintenance_visits',
    'visit_technicians',
    'faults',
    'fault_technicians',
    'parts_billing',
    'revenues',
    'expenses',
    'invoices',
    'stock_movements',
    'purchase_orders',
    'purchase_order_lines',
    'elevator_estimates',
    'elevator_estimate_lines',
    'audit_logs',
    'app_live_state',
    'installation_leads',
    'installation_projects',
    'installation_quotations',
    'installation_quotation_lines',
    'installation_timeline_steps',
]


def _sqlite_url(path: str) -> str:
    return 'sqlite:///' + Path(path).resolve().as_posix()


def _copy_table(src_sess, dst_sess, table: str) -> int:
    if table not in inspect(src_sess.bind).get_table_names():
        return 0
    if table not in inspect(dst_sess.bind).get_table_names():
        return 0
    rows = src_sess.execute(text(f'SELECT * FROM {table}')).mappings().all()
    if not rows:
        return 0
    dst_sess.execute(text(f'DELETE FROM {table}'))
    cols = list(rows[0].keys())
    col_list = ', '.join(cols)
    placeholders = ', '.join(f':{c}' for c in cols)
    insert_sql = text(f'INSERT INTO {table} ({col_list}) VALUES ({placeholders})')
    for row in rows:
        dst_sess.execute(insert_sql, dict(row))
    return len(rows)


def main() -> int:
    print('Note: prefer scripts/migrate_instance_to_tenant.py for multi-tenant cutover (week 8).')
    slug = os.environ.get('MIGRATE_TENANT_SLUG', 'default')
    name = os.environ.get('MIGRATE_TENANT_NAME', 'LiftCore')
    sqlite_path = (os.environ.get('SQLITE_SOURCE') or os.environ.get('SQLITE_PATH') or '').strip()
    pg_url = (os.environ.get('DATABASE_URL') or '').strip()
    if not sqlite_path or not Path(sqlite_path).is_file():
        print('ERROR: SQLITE_SOURCE must point to an existing .db file', file=sys.stderr)
        return 1
    if not pg_url.startswith(('postgresql://', 'postgres://')):
        print('ERROR: DATABASE_URL must be PostgreSQL', file=sys.stderr)
        return 1

    from scripts.migrate_instance_to_tenant import migrate_instance

    uploads = os.environ.get('UPLOADS_SOURCE', '').strip() or None
    report = migrate_instance(
        sqlite_path=sqlite_path,
        slug=slug,
        name=name,
        target_url=pg_url,
        uploads_source=uploads,
        dry_run=False,
        force=os.environ.get('MIGRATE_FORCE', '').strip().lower() in ('1', 'true', 'yes'),
    )
    print('Done.', report['total_rows'], 'rows, slug=', report['slug'])
    return 0


def _main_legacy() -> int:
    sqlite_path = (os.environ.get('SQLITE_SOURCE') or os.environ.get('SQLITE_PATH') or '').strip()
    pg_url = (os.environ.get('DATABASE_URL') or '').strip()
    if not sqlite_path or not Path(sqlite_path).is_file():
        print('ERROR: SQLITE_SOURCE must point to an existing .db file', file=sys.stderr)
        return 1
    if not pg_url.startswith(('postgresql://', 'postgres://')):
        print('ERROR: DATABASE_URL must be PostgreSQL', file=sys.stderr)
        return 1

    from liftcore_database import normalize_database_url, reset_postgres_sequences

    pg_url = normalize_database_url(pg_url)
    os.environ['DATABASE_URL'] = pg_url
    os.environ['LIFTCORE_ALEMBIC'] = '1'

    from deploy.migrate_db import main as run_migrations

    print('[1/3] Alembic upgrade on PostgreSQL...')
    if run_migrations() != 0:
        return 1

    print('[2/3] Copying data...')
    src_engine = create_engine(_sqlite_url(sqlite_path))
    dst_engine = create_engine(pg_url)
    Src = sessionmaker(bind=src_engine)
    Dst = sessionmaker(bind=dst_engine)
    counts: dict[str, int] = {}
    with Src() as src_sess, Dst() as dst_sess:
        for table in COPY_ORDER:
            n = _copy_table(src_sess, dst_sess, table)
            if n:
                counts[table] = n
                print(f'  {table}: {n} rows')
        dst_sess.commit()
        with dst_engine.begin() as conn:
            reset_postgres_sequences(conn, [t for t in COPY_ORDER if t in counts])

    print('[3/3] Done. Counts:', sum(counts.values()), 'rows in', len(counts), 'tables')
    print('Set DATABASE_URL in platform.env and restart liftcore service.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
