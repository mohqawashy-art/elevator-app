"""ربط تقدير المصعد بمشروع/عرض التركيب

Revision ID: h7h2week29_estimate_quote_link
Revises: g6g1week28_sales_maint_quotes
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'h7h2week29_estimate_quote_link'
down_revision = 'g6g1week28_sales_maint_quotes'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'elevator_estimates' not in insp.get_table_names():
        return
    cols = {c['name'] for c in insp.get_columns('elevator_estimates')}
    if 'result_project_id' not in cols:
        op.add_column('elevator_estimates', sa.Column('result_project_id', sa.Integer(), nullable=True))
        op.create_index('ix_elevator_estimates_result_project_id', 'elevator_estimates', ['result_project_id'])
    if 'result_quotation_id' not in cols:
        op.add_column('elevator_estimates', sa.Column('result_quotation_id', sa.Integer(), nullable=True))
        op.create_index('ix_elevator_estimates_result_quotation_id', 'elevator_estimates', ['result_quotation_id'])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'elevator_estimates' not in insp.get_table_names():
        return
    cols = {c['name'] for c in insp.get_columns('elevator_estimates')}
    if 'result_quotation_id' in cols:
        try:
            op.drop_index('ix_elevator_estimates_result_quotation_id', table_name='elevator_estimates')
        except Exception:
            pass
        op.drop_column('elevator_estimates', 'result_quotation_id')
    if 'result_project_id' in cols:
        try:
            op.drop_index('ix_elevator_estimates_result_project_id', table_name='elevator_estimates')
        except Exception:
            pass
        op.drop_column('elevator_estimates', 'result_project_id')
