"""ترقيات مخطط موديول التركيب — قيود فريدة متعددة المستأجرين."""
from __future__ import annotations

from sqlalchemy import inspect, text

from models import db

# جداول كانت Unique(code) عالمياً في baseline ثم صارت (organization_id, code)
_INSTALL_CODE_TABLES = (
    ('installation_leads', 'installation_leads_code_key', 'uq_install_lead_org_code'),
    ('installation_projects', 'installation_projects_code_key', 'uq_install_project_org_code'),
    ('installation_quotations', 'installation_quotations_code_key', 'uq_install_quote_org_code'),
)


def ensure_install_quote_columns() -> None:
    """عمود جدول الدفعات الحر — يُضاف على Postgres/SQLite إن غاب."""
    insp = inspect(db.engine)
    try:
        insp.clear_cache()
    except Exception:
        pass
    tables = set(insp.get_table_names())
    if 'installation_quotations' not in tables:
        return
    cols = {c['name'] for c in insp.get_columns('installation_quotations')}
    if 'pay_schedule_json' in cols:
        return
    db.session.execute(text(
        'ALTER TABLE installation_quotations ADD COLUMN pay_schedule_json TEXT'
    ))
    db.session.commit()


def ensure_install_tenant_uniques() -> None:
    """استبدال UNIQUE(code) العالمي بـ UNIQUE(organization_id, code).

    بدون ذلك مستأجر جديد يفشل عند LD-0001 إذا كان الكود مستخدماً عند مستأجر آخر.
    """
    ensure_install_quote_columns()
    dialect = (db.engine.dialect.name or '').lower()
    if dialect == 'postgresql':
        _ensure_postgres()
        return
    _ensure_via_inspector(dialect)


def _ensure_postgres() -> None:
    """مسار Postgres مباشر — لا يعتمد على inspector فقط."""
    for table, legacy_name, org_uq_name in _INSTALL_CODE_TABLES:
        exists = db.session.execute(text(
            'SELECT to_regclass(:t) IS NOT NULL'
        ), {'t': table}).scalar()
        if not exists:
            continue
        db.session.execute(text(
            f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {legacy_name}'
        ))
        db.session.execute(text(f'DROP INDEX IF EXISTS {legacy_name}'))
        # أي فهرس/قيد فريد على code وحده بأسماء أخرى
        rows = db.session.execute(text('''
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY (c.conkey)
            WHERE t.relname = :table
              AND c.contype = 'u'
              AND array_length(c.conkey, 1) = 1
              AND a.attname = 'code'
        '''), {'table': table}).fetchall()
        for (conname,) in rows:
            if conname:
                db.session.execute(text(
                    f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {conname}'
                ))
        db.session.execute(text(
            f'CREATE UNIQUE INDEX IF NOT EXISTS {org_uq_name} '
            f'ON {table} (organization_id, code)'
        ))
    db.session.commit()


def _ensure_via_inspector(dialect: str) -> None:
    insp = inspect(db.engine)
    try:
        insp.clear_cache()
    except Exception:
        pass
    tables = set(insp.get_table_names())

    for table, _legacy, org_uq_name in _INSTALL_CODE_TABLES:
        if table not in tables:
            continue
        cols = {c['name'] for c in insp.get_columns(table)}
        if 'organization_id' not in cols or 'code' not in cols:
            continue

        for uc in insp.get_unique_constraints(table):
            col_names = list(uc.get('column_names') or [])
            name = uc.get('name')
            if col_names == ['code'] and name:
                _drop_unique(dialect, table, name)

        for ix in insp.get_indexes(table):
            if not ix.get('unique'):
                continue
            col_names = list(ix.get('column_names') or [])
            name = ix.get('name')
            if col_names == ['code'] and name:
                _drop_index(dialect, name)

        try:
            insp.clear_cache()
        except Exception:
            pass
        unique_constraints = inspect(db.engine).get_unique_constraints(table)
        indexes = inspect(db.engine).get_indexes(table)
        has_org_code = any(
            list(uc.get('column_names') or []) in (
                ['organization_id', 'code'], ['code', 'organization_id']
            )
            for uc in unique_constraints
        ) or any(
            ix.get('unique') and list(ix.get('column_names') or []) in (
                ['organization_id', 'code'], ['code', 'organization_id']
            )
            for ix in indexes
        )
        if not has_org_code:
            _create_org_code_unique(dialect, table, org_uq_name)


def _drop_unique(dialect: str, table: str, name: str) -> None:
    try:
        if dialect == 'postgresql':
            db.session.execute(text(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}'))
        else:
            db.session.execute(text(f'ALTER TABLE {table} DROP CONSTRAINT {name}'))
        db.session.commit()
    except Exception:
        db.session.rollback()
        _drop_index(dialect, name)


def _drop_index(dialect: str, name: str) -> None:
    try:
        db.session.execute(text(f'DROP INDEX IF EXISTS {name}'))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _create_org_code_unique(dialect: str, table: str, name: str) -> None:
    try:
        db.session.execute(text(
            f'CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table} (organization_id, code)'
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
