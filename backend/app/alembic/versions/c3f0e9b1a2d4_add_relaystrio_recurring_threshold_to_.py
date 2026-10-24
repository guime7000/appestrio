"""add relaystrio_recurring_threshold_days to lora_settings table

Revision ID: c3f0e9b1a2d4
Revises: 81b1c47cc2a5
Create Date: 2026-10-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3f0e9b1a2d4'
down_revision = '81b1c47cc2a5'
branch_labels = None
depends_on = None

# Repeated here rather than imported from app code, same pattern as every
# other migration in this directory -- a migration's seed/backfill data
# must stand on its own.
DEFAULT_RELAYSTRIO_RECURRING_THRESHOLD_DAYS = 2


def upgrade():
    # NOT NULL requires a server default so the existing singleton row
    # backfills to the real default rather than NULL.
    op.add_column(
        'lora_settings',
        sa.Column(
            'relaystrio_recurring_threshold_days',
            sa.Integer(),
            nullable=False,
            server_default=sa.text(str(DEFAULT_RELAYSTRIO_RECURRING_THRESHOLD_DAYS)),
        ),
    )


def downgrade():
    op.drop_column('lora_settings', 'relaystrio_recurring_threshold_days')
