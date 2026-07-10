"""جدول/أعمدة ZATCA Phase 2 على الفواتير

Revision ID: i9g4week11zatca2
Revises: h8f3week10billing
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'i9g4week11zatca2'
down_revision = 'h8f3week10billing'
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return column in {c['name'] for c in insp.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    cols = (
        ('zatca_uuid', sa.String(length=64)),
        ('zatca_invoice_hash', sa.String(length=128)),
        ('zatca_qr_payload', sa.Text()),
        ('zatca_status', sa.String(length=20)),
        ('zatca_reported_at', sa.DateTime()),
        ('zatca_last_error', sa.Text()),
    )
    for name, col_type in cols:
        if not _has_column(bind, 'invoices', name):
            op.add_column('invoices', sa.Column(name, col_type, nullable=True))


def downgrade():
    bind = op.get_bind()
    for name in (
        'zatca_last_error',
        'zatca_reported_at',
        'zatca_status',
        'zatca_qr_payload',
        'zatca_invoice_hash',
        'zatca_uuid',
    ):
        if _has_column(bind, 'invoices', name):
            op.drop_column('invoices', name)
