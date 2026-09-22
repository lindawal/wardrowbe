"""consolidate occasions into work / casual / going-out

Revision ID: 90e4ebe3930d
Revises: f7a8b9c0d1e2
Create Date: 2026-09-22

The occasion vocabulary had drifted into three inconsistent lists: the
outfit/suggestion/studio/photo-look endpoints in api/outfits.py accepted 22
free-form values, notification schedules (schemas/notification.py) accepted
a different 8, and the frontend only ever offered 6 of those. This collapses
all of it down to three: work, casual, going-out. Remaps existing values on
outfits, schedules, user_preferences, and outfit_performances accordingly.

Learned-preference JSONB blobs (UserLearningProfile.learned_occasion_patterns
and .learned_temporal_patterns, ItemPairScore.occasion_performance) are left
untouched — their keys just stop matching current occasions and the app
relearns them under the new three over time. Nothing reads a stale key as if
it were a new one, so this is safe to leave.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "90e4ebe3930d"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# old occasion value -> new value. Anything not listed here (including "casual"
# and "work", which are unchanged) and not already a new value gets the
# fallback below.
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

_TABLES_COLUMNS = [
    ("outfits", "occasion"),
    ("schedules", "occasion"),
    ("user_preferences", "default_occasion"),
    ("outfit_performances", "occasion"),
]

_NEW_VALUES = ("work", "casual", "going-out")

# Reverse of the merge: only used by downgrade(), which cannot recover values
# that were merged together (e.g. "sporty" and "outdoor" both became
# "casual"). It restores one representative predecessor per new value instead.
_DOWNGRADE_MAP = {"work": "office", "going-out": "date"}


def upgrade() -> None:
    conn = op.get_bind()
    for table, column in _TABLES_COLUMNS:
        for old, new in _REMAP.items():
            conn.execute(
                sa.text(f'UPDATE {table} SET "{column}" = :new WHERE "{column}" = :old'),
                {"new": new, "old": old},
            )
        # Anything still outside the new vocabulary (custom values the old,
        # more permissive API accepted, or hand-edited rows) falls back to
        # "casual", matching the app's own default for an unrecognized occasion.
        placeholders = ", ".join(f"'{v}'" for v in _NEW_VALUES)
        conn.execute(
            sa.text(f'UPDATE {table} SET "{column}" = \'casual\' WHERE "{column}" NOT IN ({placeholders})')
        )


def downgrade() -> None:
    conn = op.get_bind()
    for table, column in _TABLES_COLUMNS:
        for new, old in _DOWNGRADE_MAP.items():
            conn.execute(
                sa.text(f'UPDATE {table} SET "{column}" = :old WHERE "{column}" = :new'),
                {"old": old, "new": new},
            )
