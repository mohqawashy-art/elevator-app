"""استبدال UNIQUE(code) العالمي بـ UNIQUE(organization_id, code) للمستأجرين

Revision ID: m3k8week12tenantcode
Revises: l2j7week11customervat
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'm3k8week12tenantcode'
down_revision = 'l2j7week11customervat'
branch_labels = None
depends_on = None

# (table, composite_constraint_name)
CODE_TABLES = (
    ('customers', 'uq_customer_org_code'),
    ('elevators', 'uq_elevator_org_code'),
    ('contracts', 'uq_contract_org_code'),
    ('technicians', 'uq_technician_org_code'),
    ('maintenance_teams', 'uq_mteam_org_code'),
    ('maintenance_visits', 'uq_visit_org_code'),
    ('faults', 'uq_fault_org_code'),
    ('revenues', 'uq_revenue_org_code'),
    ('expenses', 'uq_expense_org_code'),
    ('invoices', 'uq_invoice_org_code'),
    ('inventory_items', 'uq_inventory_org_code'),
    ('stock_movements', 'uq_stockmv_org_code'),
    ('parts_billing', 'uq_partsbill_org_code'),
    ('purchase_orders', 'uq_po_org_code'),
    ('elevator_estimates', 'uq_est_org_code'),
)


def _table_exists(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def _unique_names(bind, table: str) -> set[str]:
    insp = sa.inspect(bind)
    names = {u['name'] for u in (insp.get_unique_constraints(table) or []) if u.get('name')}
    for ix in insp.get_indexes(table) or []:
        if ix.get('unique') and ix.get('name'):
            names.add(ix['name'])
    return names


def _has_named_unique(bind, table: str, name: str) -> bool:
    return name in _unique_names(bind, table)


def _drop_global_code_unique(bind, table: str) -> None:
    """أسقط UNIQUE على عمود code وحده (مثل customers_code_key)."""
    insp = sa.inspect(bind)
    dialect = bind.dialect.name

    for uq in insp.get_unique_constraints(table) or []:
        cols = list(uq.get('column_names') or [])
        name = uq.get('name')
        if cols == ['code'] and name:
            if dialect == 'sqlite':
                with op.batch_alter_table(table) as batch_op:
                    batch_op.drop_constraint(name, type_='unique')
            else:
                op.drop_constraint(name, table_name=table, type_='unique')
            return

    for ix in insp.get_indexes(table) or []:
        if ix.get('unique') and list(ix.get('column_names') or []) == ['code']:
            name = ix.get('name')
            if name:
                op.drop_index(name, table_name=table)
            return


def upgrade():
    bind = op.get_bind()
    for table, uq_name in CODE_TABLES:
        if not _table_exists(bind, table):
            continue
        cols = {c['name'] for c in sa.inspect(bind).get_columns(table)}
        if 'organization_id' not in cols or 'code' not in cols:
            continue

        _drop_global_code_unique(bind, table)

        if not _has_named_unique(bind, table, uq_name):
            op.execute(sa.text(
                f'CREATE UNIQUE INDEX IF NOT EXISTS {uq_name} '
                f'ON {table} (organization_id, code)'
            ))


def downgrade():
    bind = op.get_bind()
    for table, uq_name in reversed(CODE_TABLES):
        if not _table_exists(bind, table):
            continue
        if _has_named_unique(bind, table, uq_name):
            op.drop_index(uq_name, table_name=table)
        # لا نُعيد UNIQUE(code) العالمي — يكسر تعدد المستأجرين
