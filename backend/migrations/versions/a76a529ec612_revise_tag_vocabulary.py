"""revise item tag vocabulary (formality, style, pattern, material, colors, season, fit)

Revision ID: a76a529ec612
Revises: bb088f451a0c
Create Date: 2026-09-25

Part of trimming and cleaning up the tag vocabularies the AI tagger and the item
editor offer (see backend/app/services/ai_service.py VALID_FORMALITY,
VALID_STYLES, VALID_PATTERNS, VALID_MATERIALS, VALID_COLORS, VALID_SEASONS,
VALID_FIT). None of clothing_items.formality/pattern/material/style/season is a
CHECK-constrained column, so this only needs to touch the changes that have a
clear 1:1 successor value -- everything else is a pure removal with nothing to
rename to, and is left as free text on any pre-existing item (same choice made
in 7ae608b1233e for the clothing-type vocabulary): it just won't be offered by
the editor or re-assigned by AI tagging any more.

Migrated here:
- formality: "very-casual" -> "casual", "business-casual" -> "formal",
  "very-formal" -> "formal" (the 5/6-level scale collapses to casual /
  smart-casual / formal; "very-formal" was never actually reachable, since it
  was never in VALID_FORMALITY despite being referenced by the going-out
  occasion mapping and FORMALITY_ORDER -- migrated anyway in case any row was
  ever set to it by hand).
- style (array column): "sporty" -> "athletic" (the two overlapping style tags
  are merged; de-duplicated in case an item already carried both).
- pattern: "graphic" -> "print" (pure rename, same meaning).

Left as orphaned free text, no migration (no successor value):
- formality: none other.
- style: "modern", "classic", "preppy".
- pattern: "plaid", "camouflage".
- material: "linen", "nylon".
- colors / primary_color: "tan", "cream".
- fit (JSON-only, not a column -- see frontend/lib/item-tags.ts): "tailored".
- season (array column): "all-season" -- functionally identical to an empty
  season list (see the "not seasons or 'all-season' in seasons" check in
  item_scorer._season_score, kept for this exact reason), so no data migration
  is needed for existing rows to keep scoring correctly.

New value with nothing to migrate from: colors "dark-green". Season vocabulary
is otherwise unchanged (spring/summer/fall/winter).

Downgrade note: the formality and style merges above are not reversible --
which original value a row had is no longer known once two values collapse
into one. This is harmless for the pre-migration code, though, since every
post-migration value ("casual", "formal", "athletic") was already a valid
value in the wider vocabulary it replaces, so downgrade leaves those columns
alone rather than guessing.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a76a529ec612"
down_revision: str | None = "bb088f451a0c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FORMALITY_RENAME = {
    "very-casual": "casual",
    "business-casual": "formal",
    "very-formal": "formal",
}


def upgrade() -> None:
    conn = op.get_bind()

    for old, new in _FORMALITY_RENAME.items():
        conn.execute(
            sa.text('UPDATE clothing_items SET formality = :new WHERE formality = :old'),
            {"new": new, "old": old},
        )

    conn.execute(
        sa.text(
            "UPDATE clothing_items SET pattern = 'print' WHERE pattern = 'graphic'"
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE clothing_items
            SET style = (
                SELECT ARRAY(SELECT DISTINCT unnest(array_replace(style, 'sporty', 'athletic')))
            )
            WHERE 'sporty' = ANY(style)
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Formality and style merged distinct values into one each, so which
    # original value a row had is no longer known -- there is nothing to
    # convert back for either column (see the module docstring). Only the
    # pattern rename is a clean, reversible 1:1 mapping.
    conn.execute(
        sa.text(
            "UPDATE clothing_items SET pattern = 'graphic' WHERE pattern = 'print'"
        )
    )
