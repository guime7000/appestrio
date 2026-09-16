"""add last_seen and last_roundtrip_ms to devices table

Revision ID: 81b9a2129d62
Revises: ae5f47a6faf2
Create Date: 2026-09-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "81b9a2129d62"
down_revision = "ae5f47a6faf2"
branch_labels = None
depends_on = None


def upgrade():
    # Both nullable, no default -- existing rows correctly backfill to
    # "never seen" (None) rather than a fabricated timestamp, since no
    # daemon has ever pinged them.
    op.add_column("devices", sa.Column("last_seen", sa.DateTime(), nullable=True))
    op.add_column("devices", sa.Column("last_roundtrip_ms", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("devices", "last_roundtrip_ms")
    op.drop_column("devices", "last_seen")
