"""جدول zatca_credentials + ترحيل الرقم الضريبي من settings

Revision ID: e5c0week6zatca
Revises: d4b9week4install
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'e5c0week6zatca'
down_revision = 'd4b9week4install'
branch_labels = None
depends_on = None


def _table_exists(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if not _table_exists(bind, 'zatca_credentials'):
        op.create_table(
            'zatca_credentials',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('organization_id', sa.Integer(), nullable=False),
            sa.Column('vat_number', sa.String(length=15), nullable=False),
            sa.Column('cr_number', sa.String(length=20), nullable=True),
            sa.Column('csid', sa.Text(), nullable=True),
            sa.Column('private_key', sa.Text(), nullable=True),
            sa.Column('certificate', sa.Text(), nullable=True),
            sa.Column('environment', sa.String(length=10), nullable=True),
            sa.Column('onboarded_at', sa.DateTime(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('organization_id', name='uq_zatca_credentials_org'),
        )
        op.create_index(
            'ix_zatca_credentials_organization_id',
            'zatca_credentials',
            ['organization_id'],
            unique=False,
        )

    if _table_exists(bind, 'settings') and _table_exists(bind, 'zatca_credentials'):
        op.execute(sa.text(
            'INSERT INTO zatca_credentials (organization_id, vat_number, cr_number, status, environment) '
            'SELECT s.organization_id, TRIM(s.vat_number), TRIM(s.cr_number), '
            "'active', 'sandbox' "
            'FROM settings s '
            'WHERE s.vat_number IS NOT NULL AND TRIM(s.vat_number) != \'\' '
            'AND NOT EXISTS ('
            '  SELECT 1 FROM zatca_credentials z WHERE z.organization_id = s.organization_id'
            ')'
        ))


def downgrade():
    bind = op.get_bind()
    if _table_exists(bind, 'zatca_credentials'):
        op.drop_index('ix_zatca_credentials_organization_id', table_name='zatca_credentials')
        op.drop_table('zatca_credentials')
