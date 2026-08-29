"""add handles_audio and handles_dmx to devices table

Revision ID: 471f0e23e888
Revises: 57abfb69d5f1
Create Date: 2026-08-29 23:06:35.118007

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '471f0e23e888'
down_revision = '57abfb69d5f1'
branch_labels = None
depends_on = None


def upgrade():
    # NOT NULL requires a server default so existing rows backfill to False.
    op.add_column(
        'devices',
        sa.Column('handles_audio', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'devices',
        sa.Column('handles_dmx', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column('devices', 'handles_dmx')
    op.drop_column('devices', 'handles_audio')
