"""حسابات مؤسسة نسق كور — فواتير ومصاريف وسندات قبض

Revision ID: g8h2w41_nasq_core_books
Revises: f6f0w40_ext_elev_insp
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'g8h2w41_nasq_core_books'
down_revision = 'f6f0w40_ext_elev_insp'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def _has_column(bind, table: str, column: str) -> bool:
    if not _has_table(bind, table):
        return False
    return column in {c['name'] for c in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, 'platform_invoices'):
        op.create_table(
            'platform_invoices',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('code', sa.String(length=30), nullable=False),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
            sa.Column('description', sa.String(length=300)),
            sa.Column('period_start', sa.DateTime()),
            sa.Column('period_end', sa.DateTime()),
            sa.Column('subtotal', sa.Float(), nullable=False),
            sa.Column('tax_pct', sa.Float()),
            sa.Column('tax_amount', sa.Float()),
            sa.Column('total', sa.Float(), nullable=False),
            sa.Column('currency', sa.String(length=10)),
            sa.Column('status', sa.String(length=20)),
            sa.Column('issue_date', sa.DateTime()),
            sa.Column('due_date', sa.DateTime()),
            sa.Column('paid_at', sa.DateTime()),
            sa.Column('notes', sa.Text()),
            sa.Column('created_by_user_id', sa.Integer()),
            sa.Column('created_at', sa.DateTime()),
        )
        op.create_index('ix_platform_invoices_code', 'platform_invoices', ['code'], unique=True)
        op.create_index('ix_platform_invoices_organization_id', 'platform_invoices', ['organization_id'])
        op.create_index('ix_platform_invoices_status', 'platform_invoices', ['status'])

    if not _has_table(bind, 'platform_expenses'):
        op.create_table(
            'platform_expenses',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('code', sa.String(length=30), nullable=False),
            sa.Column('spent_at', sa.DateTime()),
            sa.Column('category', sa.String(length=40)),
            sa.Column('vendor', sa.String(length=200)),
            sa.Column('description', sa.String(length=400), nullable=False),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('currency', sa.String(length=10)),
            sa.Column('method', sa.String(length=40)),
            sa.Column('reference', sa.String(length=100)),
            sa.Column('notes', sa.Text()),
            sa.Column('created_by_user_id', sa.Integer()),
            sa.Column('created_at', sa.DateTime()),
        )
        op.create_index('ix_platform_expenses_code', 'platform_expenses', ['code'], unique=True)
        op.create_index('ix_platform_expenses_spent_at', 'platform_expenses', ['spent_at'])

    if _has_table(bind, 'platform_payments'):
        if not _has_column(bind, 'platform_payments', 'invoice_id'):
            op.add_column('platform_payments', sa.Column('invoice_id', sa.Integer(), nullable=True))
            op.create_index('ix_platform_payments_invoice_id', 'platform_payments', ['invoice_id'])
            op.create_foreign_key(
                'fk_platform_payments_invoice_id',
                'platform_payments',
                'platform_invoices',
                ['invoice_id'],
                ['id'],
            )
        if not _has_column(bind, 'platform_payments', 'receipt_code'):
            op.add_column('platform_payments', sa.Column('receipt_code', sa.String(length=30), nullable=True))
            op.create_index('ix_platform_payments_receipt_code', 'platform_payments', ['receipt_code'], unique=True)
        if not _has_column(bind, 'platform_payments', 'receipt_issued_at'):
            op.add_column('platform_payments', sa.Column('receipt_issued_at', sa.DateTime(), nullable=True))


def downgrade():
    bind = op.get_bind()
    if _has_column(bind, 'platform_payments', 'receipt_issued_at'):
        op.drop_column('platform_payments', 'receipt_issued_at')
    if _has_column(bind, 'platform_payments', 'receipt_code'):
        op.drop_index('ix_platform_payments_receipt_code', table_name='platform_payments')
        op.drop_column('platform_payments', 'receipt_code')
    if _has_column(bind, 'platform_payments', 'invoice_id'):
        op.drop_constraint('fk_platform_payments_invoice_id', 'platform_payments', type_='foreignkey')
        op.drop_index('ix_platform_payments_invoice_id', table_name='platform_payments')
        op.drop_column('platform_payments', 'invoice_id')
    if _has_table(bind, 'platform_expenses'):
        op.drop_table('platform_expenses')
    if _has_table(bind, 'platform_invoices'):
        op.drop_table('platform_invoices')
