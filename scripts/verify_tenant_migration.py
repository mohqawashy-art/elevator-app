#!/usr/bin/env python3
"""التحقق بعد ترحيل tenant — أسبوع 8."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

CHECK_TABLES = (
    'customers',
    'elevators',
    'contracts',
    'maintenance_visits',
    'invoices',
    'users',
    'settings',
)


def verify(slug: str, expected: dict[str, int] | None = None, *, database_url: str | None = None) -> dict:
    from sqlalchemy import create_engine, inspect as sa_inspect, text
    from liftcore_database import normalize_database_url

    slug = {'app': 'default', 'liftcore': 'default'}.get(slug, slug)
    report: dict = {'slug': slug, 'ok': True, 'tables': {}, 'errors': []}

    url = normalize_database_url(database_url or os.environ.get('DATABASE_URL') or '')
    if not url:
        report['ok'] = False
        report['errors'].append('DATABASE_URL not set')
        return report

    engine = create_engine(url)
    try:
        insp = sa_inspect(engine)
        with engine.connect() as conn:
            org = conn.execute(
                text('SELECT id, name, status FROM organizations WHERE slug = :slug'),
                {'slug': slug},
            ).mappings().first()
            if not org:
                report['ok'] = False
                report['errors'].append(f'organization slug={slug!r} not found')
                return report

            oid = int(org['id'])
            report['organization_id'] = oid
            report['organization_name'] = org['name']
            report['organization_status'] = org['status']

            for table in CHECK_TABLES:
                if table not in insp.get_table_names():
                    continue
                total = conn.execute(
                    text(f'SELECT COUNT(*) FROM {table} WHERE organization_id = :oid'),
                    {'oid': oid},
                ).scalar()
                leaked = conn.execute(
                    text(
                        f'SELECT COUNT(*) FROM {table} WHERE organization_id IS NOT NULL '
                        f'AND organization_id != :oid'
                    ),
                    {'oid': oid},
                ).scalar()
                cnt = int(total or 0)
                report['tables'][table] = cnt
                if expected and table in expected and expected[table] != cnt:
                    report['ok'] = False
                    report['errors'].append(
                        f'{table}: expected {expected[table]}, got {cnt}',
                    )
                if leaked:
                    report['ok'] = False
                    report['errors'].append(f'{table}: {leaked} rows with wrong organization_id')

            admin = conn.execute(
                text(
                    "SELECT COUNT(*) FROM users WHERE organization_id = :oid AND role = 'admin'"
                ),
                {'oid': oid},
            ).scalar()
            report['admin_users'] = int(admin or 0)
            if report['admin_users'] < 1:
                report['ok'] = False
                report['errors'].append('no admin user for tenant')

            settings = conn.execute(
                text('SELECT COUNT(*) FROM settings WHERE organization_id = :oid'),
                {'oid': oid},
            ).scalar()
            report['settings_rows'] = int(settings or 0)
            if report['settings_rows'] < 1:
                report['ok'] = False
                report['errors'].append('no settings row for tenant')

            if 'zatca_credentials' in insp.get_table_names():
                zatca = conn.execute(
                    text('SELECT COUNT(*) FROM zatca_credentials WHERE organization_id = :oid'),
                    {'oid': oid},
                ).scalar()
                report['zatca_credentials'] = int(zatca or 0)
    finally:
        engine.dispose()

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Verify tenant migration counts')
    parser.add_argument('--slug', default='default')
    parser.add_argument('--expect-customers', type=int, default=0)
    args = parser.parse_args(argv)

    expected = {}
    if args.expect_customers:
        expected['customers'] = args.expect_customers

    report = verify(args.slug, expected or None)
    status = 'OK' if report['ok'] else 'FAIL'
    print(f'[{status}] slug={report["slug"]} org_id={report.get("organization_id")}')
    for table, n in report.get('tables', {}).items():
        print(f'  {table}: {n}')
    if report.get('zatca_credentials') is not None:
        print(f'  zatca_credentials: {report["zatca_credentials"]}')
    for err in report.get('errors', []):
        print(f'  ERROR: {err}', file=sys.stderr)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
