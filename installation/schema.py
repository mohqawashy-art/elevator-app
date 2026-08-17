"""ترقيات مخطط موديول التركيب — قيود فريدة متعددة المستأجرين."""
from __future__ import annotations

from sqlalchemy import inspect, text

from models import db

# جداول كانت Unique(code) عالمياً في baseline ثم صارت (organization_id, code)
_INSTALL_CODE_TABLES = (
    ('installation_leads', 'uq_install_lead_org_code'),
    ('installation_projects', 'uq_install_project_org_code'),
    ('installation_quotations', 'uq_install_quote_org_code'),
)


def ensure_install_tenant_uniques() -> None:
    """استبدال UNIQUE(code) العالمي بـ UNIQUE(organization_id, code).

    بدون ذلك مستأجر جديد يفشل عند LD-0001 إذا كان الكود مستخدماً عند مستأجر آخر.
    """
    dialect = (db.engine.dialect.name or '').lower()
    insp = inspect(db.engine)
    try:
        insp.clear_cache()
    except Exception:
        pass
    tables = set(insp.get_table_names())

    for table, org_uq_name in _INSTALL_CODE_TABLES:
        if table not in tables:
            continue
        cols = {c['name'] for c in insp.get_columns(table)}
        if 'organization_id' not in cols or 'code' not in cols:
            continue

        unique_constraints = insp.get_unique_constraints(table)
        indexes = insp.get_indexes(table)

        # إسقاط UNIQUE على code وحده
        for uc in unique_constraints:
            col_names = list(uc.get('column_names') or [])
            name = uc.get('name')
            if col_names == ['code'] and name:
                _drop_unique(dialect, table, name)

        for ix in indexes:
            if not ix.get('unique'):
                continue
            col_names = list(ix.get('column_names') or [])
            name = ix.get('name')
            if col_names == ['code'] and name:
                _drop_index(dialect, name)

        # إنشاء قيد المستأجر إن غاب
        try:
            insp.clear_cache()
        except Exception:
            pass
        unique_constraints = inspect(db.engine).get_unique_constraints(table)
        indexes = inspect(db.engine).get_indexes(table)
        has_org_code = any(
            list(uc.get('column_names') or []) == ['organization_id', 'code']
            or list(uc.get('column_names') or []) == ['code', 'organization_id']
            for uc in unique_constraints
        ) or any(
            ix.get('unique') and (
                list(ix.get('column_names') or []) == ['organization_id', 'code']
                or list(ix.get('column_names') or []) == ['code', 'organization_id']
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
        # SQLite أحياناً يخزّنها كفهرس
        _drop_index(dialect, name)


def _drop_index(dialect: str, name: str) -> None:
    try:
        if dialect == 'postgresql':
            db.session.execute(text(f'DROP INDEX IF EXISTS {name}'))
        else:
            db.session.execute(text(f'DROP INDEX IF EXISTS {name}'))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _create_org_code_unique(dialect: str, table: str, name: str) -> None:
    try:
        if dialect == 'postgresql':
            db.session.execute(text(
                f'CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table} (organization_id, code)'
            ))
        else:
            db.session.execute(text(
                f'CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table} (organization_id, code)'
            ))
        db.session.commit()
    except Exception:
        db.session.rollback()
