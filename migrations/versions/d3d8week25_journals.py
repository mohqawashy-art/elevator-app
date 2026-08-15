"""قيود يومية — Alembic

Revision ID: d3d8week25_journals
Revises: c2c7week24_chart_accounts
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'd3d8week25_journals'
down_revision = 'c2c7week24_chart_accounts'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, 'journal_entries'):
        op.create_table(
            'journal_entries',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=True, index=True),
            sa.Column('code', sa.String(length=20), nullable=False),
            sa.Column('entry_date', sa.Date(), nullable=False),
            sa.Column('memo', sa.String(length=400), nullable=True),
            sa.Column('source_type', sa.String(length=30), nullable=True),
            sa.Column('source_id', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), nullable=True),
            sa.Column('created_by_name', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('organization_id', 'code', name='uq_journal_org_code'),
        )
        op.create_index('ix_journal_source', 'journal_entries', ['organization_id', 'source_type', 'source_id'])
        op.create_index('ix_journal_entries_source_type', 'journal_entries', ['source_type'])
        op.create_index('ix_journal_entries_source_id', 'journal_entries', ['source_id'])
        op.create_index('ix_journal_entries_status', 'journal_entries', ['status'])

    if not _has_table(bind, 'journal_lines'):
        op.create_table(
            'journal_lines',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=True, index=True),
            sa.Column('journal_id', sa.Integer(), sa.ForeignKey('journal_entries.id'), nullable=False),
            sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id'), nullable=False),
            sa.Column('debit', sa.Float(), nullable=True),
            sa.Column('credit', sa.Float(), nullable=True),
            sa.Column('line_memo', sa.String(length=300), nullable=True),
        )
        op.create_index('ix_journal_lines_journal_id', 'journal_lines', ['journal_id'])
        op.create_index('ix_journal_lines_account_id', 'journal_lines', ['account_id'])


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, 'journal_lines'):
        op.drop_table('journal_lines')
    if _has_table(bind, 'journal_entries'):
        op.drop_table('journal_entries')
