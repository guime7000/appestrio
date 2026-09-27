"""update lora settings defaults to match relaystrio fixed radio

Revision ID: 81b1c47cc2a5
Revises: 81b9a2129d62
Create Date: 2026-09-27 23:48:55.408469

The previous default (channel=40, speed=3/4.8kbps) was legacy's own
software default (LoraState.ts's DefaultLoraState) -- but `relaystrio`'s
E32 module is hardcoded in firmware to channel=0, air rate
AIR_DATA_RATE_010_24 (speed index 2, 2.4kbps) and can never be
reconfigured remotely (see Legacy/Audits/relaystrio.md). Since every
device on one physical LoRa network must share the same channel/air-rate
to hear each other at all (it's the radio's own tuning, not a per-device
setting), any site with a `relaystrio` unit present has always had to
override the software default to match it anyway. Changing the shipped
default to already match `relaystrio` means a freshly provisioned
`lumestrio` (or the master) needs no manual PATCH to join such a network
-- see Lora_Rewrite_Plan.md's dated update for the full discussion.

Guarded by a WHERE clause matching the *old* default exactly, so a site
that already deliberately customized this singleton row (e.g. a
lumestrio-only site with no relaystrio, intentionally left at the more
efficient old default) isn't silently overwritten.
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '81b1c47cc2a5'
down_revision = '81b9a2129d62'
branch_labels = None
depends_on = None

OLD_CHANNEL = 40
OLD_SPEED = 3
NEW_CHANNEL = 0
NEW_SPEED = 2


def upgrade():
    op.execute(
        sa.text(
            "UPDATE lora_settings SET channel = :new_channel, speed = :new_speed "
            "WHERE id = 1 AND channel = :old_channel AND speed = :old_speed"
        ).bindparams(
            new_channel=NEW_CHANNEL,
            new_speed=NEW_SPEED,
            old_channel=OLD_CHANNEL,
            old_speed=OLD_SPEED,
        )
    )


def downgrade():
    op.execute(
        sa.text(
            "UPDATE lora_settings SET channel = :old_channel, speed = :old_speed "
            "WHERE id = 1 AND channel = :new_channel AND speed = :new_speed"
        ).bindparams(
            new_channel=NEW_CHANNEL,
            new_speed=NEW_SPEED,
            old_channel=OLD_CHANNEL,
            old_speed=OLD_SPEED,
        )
    )
