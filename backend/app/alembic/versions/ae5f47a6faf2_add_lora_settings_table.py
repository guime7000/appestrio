"""add lora_settings table

Revision ID: ae5f47a6faf2
Revises: 2de02cc98ee5
Create Date: 2026-09-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ae5f47a6faf2"
down_revision = "2de02cc98ee5"
branch_labels = None
depends_on = None

# Legacy defaults (LoraState.ts's DefaultLoraState) -- also the model's own
# field defaults, repeated here since a migration's seed data must stand on
# its own rather than importing from the (freely-changeable-later) app code.
DEFAULT_CHANNEL = 40
DEFAULT_SPEED = 3
DEFAULT_PING_INTERVAL_S = 5
DEFAULT_CLOCK_INTERVAL_S = 60


def upgrade():
    op.create_table(
        "lora_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("channel", sa.Integer(), nullable=False),
        sa.Column("speed", sa.Integer(), nullable=False),
        sa.Column("fec", sa.Boolean(), nullable=False),
        sa.Column("ping_interval_s", sa.Integer(), nullable=False),
        sa.Column("clock_interval_s", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    # Seed the one singleton row up front so every reader (API, daemon) can
    # assume it already exists rather than special-casing a missing row.
    op.execute(
        sa.text(
            """
            INSERT INTO lora_settings
                (id, is_active, channel, speed, fec, ping_interval_s, clock_interval_s, updated_at)
            VALUES
                (1, 0, :channel, :speed, 1, :ping_interval_s, :clock_interval_s, CURRENT_TIMESTAMP)
            """
        ).bindparams(
            channel=DEFAULT_CHANNEL,
            speed=DEFAULT_SPEED,
            ping_interval_s=DEFAULT_PING_INTERVAL_S,
            clock_interval_s=DEFAULT_CLOCK_INTERVAL_S,
        )
    )


def downgrade():
    op.drop_table("lora_settings")
