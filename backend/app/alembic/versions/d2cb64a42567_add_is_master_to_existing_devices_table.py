"""add is_master to existing devices table

Revision ID: d2cb64a42567
Revises: 276dfee2eda6
Create Date: 2026-08-02 00:47:20.287672

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2cb64a42567'
down_revision = '276dfee2eda6'
branch_labels = None
depends_on = None


def upgrade():
    # NOT NULL requires a server default so existing rows backfill to False.
    op.add_column(
        'devices',
        sa.Column('is_master', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        'ix_devices_single_master',
        'devices',
        ['is_master'],
        unique=True,
        sqlite_where=sa.text('is_master = 1'),
        postgresql_where=sa.text('is_master = true'),
    )


def downgrade():
    op.drop_index(
        'ix_devices_single_master',
        table_name='devices',
        sqlite_where=sa.text('is_master = 1'),
        postgresql_where=sa.text('is_master = true'),
    )
    op.drop_column('devices', 'is_master')
