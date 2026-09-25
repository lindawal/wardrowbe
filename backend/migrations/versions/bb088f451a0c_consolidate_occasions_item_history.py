"""consolidate occasions into work / casual / going-out - item_history

Revision ID: bb088f451a0c
Revises: 7ae608b1233e
Create Date: 2026-09-25

Follow-up to 90e4ebe3930d: that migration remapped occasion on outfits,
schedules, user_preferences, and outfit_performances, but missed
item_history.occasion (per-item wear-log entries, shown on the item detail
page's wear history). Same remap, applied to that one remaining column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bb088f451a0c"
down_revision: str | None = "7ae608b1233e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same mapping as 90e4ebe3930d.
_REMAP = {
    "office": "work",
    "business-casual": "work",
    "interview": "work",
    "sporty": "casual",
    "sport": "casual",
    "outdoor": "casual",
    "gym": "casual",
    "running": "casual",
    "hiking": "casual",
    "lounge": "casual",
    "beach": "casual",
    "travel": "casual",
    "weekend": "casual",
    "smart-casual": "casual",
    "formal": "going-out",
    "date": "going-out",
    "party": "going-out",
    "wedding": "going-out",
    "dinner": "going-out",
    "brunch": "going-out",
}

_NEW_VALUES = ("work", "casual", "going-out")

_DOWNGRADE_MAP = {"work": "office", "going-out": "date"}


def upgrade() -> None:
    conn = op.get_bind()
    for old, new in _REMAP.items():
        conn.execute(
            sa.text('UPDATE item_history SET "occasion" = :new WHERE "occasion" = :old'),
            {"new": new, "old": old},
        )
    placeholders = ", ".join(f"'{v}'" for v in _NEW_VALUES)
    conn.execute(
        sa.text(
            f'UPDATE item_history SET "occasion" = \'casual\' '
            f'WHERE "occasion" IS NOT NULL AND "occasion" NOT IN ({placeholders})'
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    for new, old in _DOWNGRADE_MAP.items():
        conn.execute(
            sa.text('UPDATE item_history SET "occasion" = :old WHERE "occasion" = :new'),
            {"old": old, "new": new},
        )
