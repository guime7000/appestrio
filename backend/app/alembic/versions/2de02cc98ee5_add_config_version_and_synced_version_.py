"""add config_version and synced_version to devices table

Revision ID: 2de02cc98ee5
Revises: 734e32e57c56
Create Date: 2026-09-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2de02cc98ee5"
down_revision = "734e32e57c56"
branch_labels = None
depends_on = None


def upgrade():
    # Existing rows have never been pushed anything over LoRa yet, so they
    # backfill as "pending sync" (config_version=1, synced_version=0) the
    # same way a freshly created device does.
    op.add_column(
        "devices",
        sa.Column("config_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "devices",
        sa.Column("synced_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("devices", "synced_version")
    op.drop_column("devices", "config_version")
