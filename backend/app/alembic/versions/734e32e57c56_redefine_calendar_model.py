"""redefine calendar model into calendars + ignition_presets

Revision ID: 734e32e57c56
Revises: 471f0e23e888
Create Date: 2026-08-30 00:00:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "734e32e57c56"
down_revision = "471f0e23e888"
branch_labels = None
depends_on = None


def upgrade():
    # Clean replacement: the old presets/days JSON shape is dropped outright
    # (pre-production dev data, per explicit product decision) in favor of a
    # calendar made of one or more ignition_preset rows plus a weekdays list.
    op.drop_column("calendars", "presets")
    op.drop_column("calendars", "days")
    op.add_column(
        "calendars",
        sa.Column("weekdays", sa.JSON(), nullable=False, server_default="[]"),
    )

    op.create_table(
        "ignition_presets",
        sa.Column(
            "name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
        ),
        sa.Column(
            "description",
            sqlmodel.sql.sqltypes.AutoString(length=1000),
            nullable=True,
        ),
        sa.Column(
            "start_date", sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False
        ),
        sa.Column(
            "stop_date", sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False
        ),
        sa.Column(
            "start_time", sqlmodel.sql.sqltypes.AutoString(length=5), nullable=False
        ),
        sa.Column(
            "stop_time", sqlmodel.sql.sqltypes.AutoString(length=5), nullable=False
        ),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("calendar_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["calendar_id"],
            ["calendars.uuid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid"),
    )


def downgrade():
    op.drop_table("ignition_presets")
    op.drop_column("calendars", "weekdays")
    op.add_column(
        "calendars",
        sa.Column("days", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "calendars",
        sa.Column("presets", sa.JSON(), nullable=False, server_default="{}"),
    )
