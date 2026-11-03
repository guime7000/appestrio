"""default lora settings is_active to true

Revision ID: 753a502581ab
Revises: c3f0e9b1a2d4
Create Date: 2026-11-04 00:33:35.874871

With the old default (`is_active=False`), a freshly provisioned
lumestrio needed a manual `PATCH /api/v1/lora-settings/` (or the Lora
Settings page's toggle) before it would do anything on the LoRa network
at all -- `lora-daemon`'s PING loop, automatic clock-sync broadcast, and
automatic config-sync loop are all gated on it. Flipping the default to
`True` means it's ready out of the box, same "ship the default that
needs no manual step" reasoning as 81b1c47cc2a5's channel/speed change.

The WHERE clause (`is_active = 0`) is here for consistency with
81b1c47cc2a5's pattern and as a no-op safety net (never touches a row
already at 1), but -- unlike that migration's specific channel/speed
*values*, which could distinguish "untouched" from "deliberately
customized" -- a boolean has only two states, so this guard can NOT
tell apart "never touched, still the old default" from "an admin
deliberately turned it off." Any such site gets flipped too. Accepted
as fine: no real deployment exists yet (every hardware-facing item in
this project is still pre-launch, see Docs/To_Be_Done.md), so there is
no real site to protect from this today.
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '753a502581ab'
down_revision = 'c3f0e9b1a2d4'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text("UPDATE lora_settings SET is_active = 1 WHERE id = 1 AND is_active = 0")
    )


def downgrade():
    op.execute(
        sa.text("UPDATE lora_settings SET is_active = 0 WHERE id = 1 AND is_active = 1")
    )
