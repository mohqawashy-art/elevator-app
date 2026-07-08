#!/usr/bin/env python3
"""ترحيل قاعدة SQLite legacy → PostgreSQL (أو SQLite) متعدد المستأجرين — أسبوع 8.

مثال — إنتاج (liftcore.db → PostgreSQL، مؤسسة default لـ app.liftcoreapp.com):

  export DATABASE_URL=postgresql://liftcore:PASS@127.0.0.1:5432/liftcore
  python scripts/migrate_instance_to_tenant.py \\
    --slug default \\
    --name "LiftCore" \\
    --sqlite instance/liftcore.db \\
    --uploads-source static/uploads \\
    --dry-run

  python scripts/migrate_instance_to_tenant.py ...   # بدون --dry-run

مثال — tenant تجريبي jama (اختياري، بعد الإنتاج أو على PG فارغ):

  python scripts/migrate_instance_to_tenant.py \\
    --slug jama \\
    --name "جما — بيئة اختبار" \\
    --sqlite /path/to/jama.db \\
    --append
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# ترتيب الإدراج — FK-safe
COPY_ORDER: tuple[str, ...] = (
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
    'revenues',
    'expenses',
    'invoices',
    'stock_movements',
    'parts_billing',
    'purchase_orders',
    'purchase_order_lines',
    'elevator_estimates',
    'elevator_estimate_lines',
    'audit_logs',
    'installation_leads',
    'installation_projects',
    'installation_quotations',
    'installation_quotation_lines',
    'installation_timeline_steps',
)

PLATFORM_TABLES = frozenset({'organizations', 'alembic_version', 'app_live_state', 'zatca_credentials'})

PATH_COLUMNS: tuple[tuple[str, str], ...] = (
    ('customers', 'building_photo_path'),
    ('technicians', 'photo_path'),
    ('technicians', 'signature_path'),
    ('technician_documents', 'file_path'),
    ('settings', 'logo_path'),
    ('settings', 'rep_signature_path'),
    ('users', 'photo_path'),
    ('signatories', 'signature_path'),
    ('contracts', 'file_path'),
    ('purchase_orders', 'pdf_path'),
)

SLUG_ALIASES = {'app': 'default', 'liftcore': 'default'}


def _sqlite_url(path: str) -> str:
    return 'sqlite:///' + Path(path).resolve().as_posix()


def _normalize_target_url(url: str) -> str:
    if url.startswith('sqlite:///'):
        raw = url[len('sqlite:///'):]
        return 'sqlite:///' + Path(raw).as_posix()
    return url


def _table_columns(engine, table: str) -> list[str]:
    if table not in inspect(engine).get_table_names():
        return []
    return [c['name'] for c in inspect(engine).get_columns(table)]


def _ensure_target_schema(target_url: str) -> None:
    """تشغيل Alembic على target_url في عملية منفصلة لتجنب تلوث db.engine."""
    env = {**os.environ, 'DATABASE_URL': target_url, 'LIFTCORE_ALEMBIC': '1'}
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'deploy' / 'migrate_db.py')],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or 'unknown error').strip()
        raise RuntimeError(f'Alembic upgrade failed: {err}')

    engine = create_engine(target_url)
    try:
        tables = set(inspect(engine).get_table_names())
        if 'organizations' not in tables:
            raise RuntimeError(
                f'Schema incomplete after migrate — organizations missing in {target_url}'
            )
    finally:
        engine.dispose()


def _org_has_tenant_data(sess, org_id: int) -> bool:
    """هل المؤسسة تحتوي بيانات tenant (غير seed Alembic الفارغ)؟"""
    for table in COPY_ORDER:
        if table not in inspect(sess.bind).get_table_names():
            continue
        cols = _table_columns(sess.bind, table)
        if 'organization_id' not in cols:
            continue
        n = sess.execute(
            text(f'SELECT COUNT(*) FROM {table} WHERE organization_id = :oid'),
            {'oid': org_id},
        ).scalar()
        if n and int(n) > 0:
            return True
    return False


def _create_organization(sess, *, slug: str, name: str, admin_email: str | None) -> int:
    existing = sess.execute(
        text('SELECT id FROM organizations WHERE slug = :slug'),
        {'slug': slug},
    ).first()
    if existing:
        return int(existing[0])

    sess.execute(
        text(
            'INSERT INTO organizations (slug, name, status, admin_email, plan) '
            'VALUES (:slug, :name, :status, :email, :plan)'
        ),
        {
            'slug': slug,
            'name': name,
            'status': 'active',
            'email': admin_email,
            'plan': 'basic',
        },
    )
    row = sess.execute(
        text('SELECT id FROM organizations WHERE slug = :slug'),
        {'slug': slug},
    ).first()
    return int(row[0])


def _delete_org_data(sess, org_id: int) -> None:
    """حذف بيانات tenant قبل إعادة الاستيراد (--force)."""
    rev_order = list(reversed(COPY_ORDER))
    for table in rev_order:
        if table not in inspect(sess.bind).get_table_names():
            continue
        cols = _table_columns(sess.bind, table)
        if 'organization_id' not in cols:
            continue
        sess.execute(
            text(f'DELETE FROM {table} WHERE organization_id = :oid'),
            {'oid': org_id},
        )


def _copy_table(
    src_sess,
    dst_sess,
    table: str,
    org_id: int,
    *,
    dry_run: bool,
) -> int:
    src_cols = _table_columns(src_sess.bind, table)
    dst_cols = _table_columns(dst_sess.bind, table)
    if not src_cols or not dst_cols:
        return 0

    rows = src_sess.execute(text(f'SELECT * FROM {table}')).mappings().all()
    if not rows:
        return 0

    use_cols = [c for c in src_cols if c in dst_cols]
    if 'organization_id' in dst_cols and 'organization_id' not in use_cols:
        use_cols.append('organization_id')

    if dry_run:
        return len(rows)

    if not dry_run and table in COPY_ORDER:
        dst_sess.execute(text(f'DELETE FROM {table} WHERE organization_id = :oid'), {'oid': org_id})

    col_list = ', '.join(use_cols)
    placeholders = ', '.join(f':{c}' for c in use_cols)
    insert_sql = text(f'INSERT INTO {table} ({col_list}) VALUES ({placeholders})')

    for raw in rows:
        payload = {c: raw.get(c) for c in use_cols if c in raw}
        if 'organization_id' in dst_cols:
            payload['organization_id'] = org_id
        dst_sess.execute(insert_sql, payload)

    return len(rows)


def _seed_zatca(dst_sess, org_id: int, *, dry_run: bool) -> int:
    if 'zatca_credentials' not in inspect(dst_sess.bind).get_table_names():
        return 0
    if 'settings' not in inspect(dst_sess.bind).get_table_names():
        return 0
    if dry_run:
        row = dst_sess.execute(
            text(
                'SELECT COUNT(*) FROM settings WHERE organization_id = :oid '
                "AND vat_number IS NOT NULL AND TRIM(vat_number) != ''"
            ),
            {'oid': org_id},
        ).scalar()
        return int(row or 0)

    dst_sess.execute(
        text('DELETE FROM zatca_credentials WHERE organization_id = :oid'),
        {'oid': org_id},
    )
    dst_sess.execute(
        text(
            'INSERT INTO zatca_credentials (organization_id, vat_number, cr_number, status, environment) '
            'SELECT :oid, TRIM(s.vat_number), TRIM(s.cr_number), '
            "'active', 'sandbox' "
            'FROM settings s '
            'WHERE s.organization_id = :oid '
            "AND s.vat_number IS NOT NULL AND TRIM(s.vat_number) != ''"
        ),
        {'oid': org_id},
    )
    return dst_sess.execute(
        text('SELECT COUNT(*) FROM zatca_credentials WHERE organization_id = :oid'),
        {'oid': org_id},
    ).scalar() or 0


def _copy_uploads(source: Path | None, dest: Path, *, dry_run: bool) -> int:
    if not source or not source.is_dir():
        return 0
    if dry_run:
        return sum(1 for _ in source.rglob('*') if _.is_file())
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for item in source.rglob('*'):
        if not item.is_file():
            continue
        rel = item.relative_to(source)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or item.stat().st_mtime > target.stat().st_mtime:
            shutil.copy2(item, target)
            copied += 1
    return copied


def _admin_email_from_source(src_sess) -> str | None:
    if 'users' not in inspect(src_sess.bind).get_table_names():
        return None
    row = src_sess.execute(
        text("SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL LIMIT 1")
    ).first()
    if row and row[0]:
        return str(row[0]).strip()
    row = src_sess.execute(
        text('SELECT email FROM users WHERE email IS NOT NULL LIMIT 1')
    ).first()
    return str(row[0]).strip() if row and row[0] else None


def migrate_instance(
    *,
    sqlite_path: str,
    slug: str,
    name: str,
    target_url: str | None = None,
    uploads_source: str | None = None,
    uploads_dest: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    append: bool = False,
) -> dict:
    slug = SLUG_ALIASES.get(slug, slug)
    sqlite_file = Path(sqlite_path)
    if not sqlite_file.is_file():
        raise FileNotFoundError(f'SQLite not found: {sqlite_path}')

    target_url = (target_url or os.environ.get('DATABASE_URL') or '').strip()
    if not target_url:
        raise ValueError('DATABASE_URL or --target-url required')

    from liftcore_database import is_postgresql, normalize_database_url, reset_postgres_sequences

    target_url = normalize_database_url(target_url)
    target_url = _normalize_target_url(target_url)
    is_pg = is_postgresql(target_url)

    if not dry_run:
        _ensure_target_schema(target_url)

    src_engine = create_engine(_sqlite_url(str(sqlite_file)))
    Src = sessionmaker(bind=src_engine)

    if dry_run:
        counts: dict[str, int] = {}
        with Src() as src_sess:
            for table in COPY_ORDER:
                if table not in inspect(src_engine).get_table_names():
                    continue
                n = len(src_sess.execute(text(f'SELECT * FROM {table}')).mappings().all())
                if n:
                    counts[table] = n
        uploads_n = _copy_uploads(
            Path(uploads_source) if uploads_source else None,
            Path(uploads_dest or ROOT / 'static' / 'uploads'),
            dry_run=True,
        )
        src_engine.dispose()
        return {
            'slug': slug,
            'organization_id': 0,
            'dry_run': True,
            'tables': counts,
            'total_rows': sum(counts.values()),
            'uploads_files': uploads_n,
            'target': 'postgresql' if is_pg else 'sqlite',
        }

    dst_engine = create_engine(target_url)
    Dst = sessionmaker(bind=dst_engine)

    counts: dict[str, int] = {}
    org_id = 0
    with Src() as src_sess, Dst() as dst_sess:
        admin_email = _admin_email_from_source(src_sess)
        existing = dst_sess.execute(
            text('SELECT id FROM organizations WHERE slug = :slug'),
            {'slug': slug},
        ).first()

        if existing and not append and not force:
            org_id = int(existing[0])
            if _org_has_tenant_data(dst_sess, org_id):
                raise RuntimeError(
                    f'Organization slug={slug!r} already exists. Use --force to replace tenant data.'
                )
        elif existing and force:
            org_id = int(existing[0])
            _delete_org_data(dst_sess, org_id)
        else:
            org_id = _create_organization(
                dst_sess, slug=slug, name=name, admin_email=admin_email,
            )

        for table in COPY_ORDER:
            n = _copy_table(src_sess, dst_sess, table, org_id, dry_run=False)
            if n:
                counts[table] = n

        if 'app_live_state' in inspect(src_engine).get_table_names():
            rows = src_sess.execute(text('SELECT id, revision FROM app_live_state')).mappings().all()
            if rows:
                dst_sess.execute(text('DELETE FROM app_live_state'))
                for raw in rows:
                    dst_sess.execute(
                        text('INSERT INTO app_live_state (id, revision) VALUES (:id, :revision)'),
                        {'id': raw.get('id', 1), 'revision': raw.get('revision', 0)},
                    )
                counts['app_live_state'] = len(rows)

        zatca_n = _seed_zatca(dst_sess, org_id, dry_run=False)
        if zatca_n:
            counts['zatca_credentials'] = int(zatca_n)

        dst_sess.commit()
        if is_pg:
            with dst_engine.begin() as conn:
                reset_postgres_sequences(conn, [t for t in COPY_ORDER if t in counts])

    up_src = Path(uploads_source) if uploads_source else None
    up_dest = Path(uploads_dest or ROOT / 'static' / 'uploads')
    uploads_n = _copy_uploads(up_src, up_dest, dry_run=dry_run)

    return {
        'slug': slug,
        'organization_id': org_id,
        'dry_run': dry_run,
        'tables': counts,
        'total_rows': sum(counts.values()),
        'uploads_files': uploads_n,
        'target': 'postgresql' if is_pg else 'sqlite',
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Migrate legacy SQLite instance to multi-tenant DB')
    parser.add_argument('--sqlite', required=True, help='Path to source .db file')
    parser.add_argument('--slug', default='default', help='Tenant slug (app → default)')
    parser.add_argument('--name', default='LiftCore', help='Organization display name')
    parser.add_argument('--target-url', default='', help='Target DATABASE_URL (default: env)')
    parser.add_argument('--uploads-source', default='', help='Source uploads directory')
    parser.add_argument('--uploads-dest', default='', help='Destination uploads (default: static/uploads)')
    parser.add_argument('--dry-run', action='store_true', help='Report only, no writes')
    parser.add_argument('--force', action='store_true', help='Replace existing tenant data')
    parser.add_argument('--append', action='store_true', help='Keep other tenants (future: ID remap)')
    args = parser.parse_args(argv)

    if args.append and not args.force:
        print('WARN: --append without ID remap — use only on empty target or unique slug', file=sys.stderr)

    try:
        report = migrate_instance(
            sqlite_path=args.sqlite,
            slug=args.slug,
            name=args.name,
            target_url=args.target_url or None,
            uploads_source=args.uploads_source or None,
            uploads_dest=args.uploads_dest or None,
            dry_run=args.dry_run,
            force=args.force,
            append=args.append,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1

    mode = 'DRY-RUN' if report['dry_run'] else 'DONE'
    print(f'[{mode}] tenant={report["slug"]} org_id={report["organization_id"]} target={report["target"]}')
    for table, n in sorted(report['tables'].items()):
        print(f'  {table}: {n}')
    print(f'  total_rows: {report["total_rows"]}')
    print(f'  uploads_files: {report["uploads_files"]}')
    if report['dry_run']:
        print('Re-run without --dry-run to apply.')
    else:
        print(f'Next: bash deploy/verify_deploy.sh https://{report["slug"]}.liftcoreapp.com')
        if report['slug'] == 'default':
            print('      bash deploy/verify_deploy.sh https://app.liftcoreapp.com')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
