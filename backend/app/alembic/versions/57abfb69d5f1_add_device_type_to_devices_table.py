"""add device_type to devices table

Revision ID: 57abfb69d5f1
Revises: d2cb64a42567
Create Date: 2026-08-29 22:29:48.673181

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '57abfb69d5f1'
down_revision = 'd2cb64a42567'
branch_labels = None
depends_on = None

device_type_enum = sa.Enum('lumestrio', 'relaystrio', name='devicetype')


def upgrade():
    device_type_enum.create(op.get_bind(), checkfirst=True)
    # NOT NULL requires a server default so existing rows backfill to
    # 'lumestrio', the only device type that existed before this column.
    op.add_column(
        'devices',
        sa.Column('device_type', device_type_enum, nullable=False, server_default='lumestrio'),
    )


def downgrade():
    op.drop_column('devices', 'device_type')
    device_type_enum.drop(op.get_bind(), checkfirst=True)
