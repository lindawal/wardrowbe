"""rename cardigan/jumpsuit item types to blouson/overall

Revision ID: 7ae608b1233e
Revises: 90e4ebe3930d
Create Date: 2026-09-24

Part of trimming the clothing-type vocabulary from 31 down to 23 types (see
frontend/lib/types.ts CLOTHING_TYPES, backend/app/services/ai_service.py
VALID_TYPES, backend/app/utils/clothing.py ITEM_ROLE). Two of the removed
types were straight renames with an unchanged role, so existing data is
migrated: "cardigan" -> "blouson" (still mid_layer) and "jumpsuit" ->
"overall" (still full_body).

The other removed types (shirt, top, polo, blazer, hoodie, tie, bag,
accessories, suit) have no equivalent survivor to remap to. clothing_items.type
is a plain string column with no CHECK constraint, so any pre-existing item
tagged with one of those keeps that value as free text -- it just won't be
offered by the type dropdown or re-assigned by AI tagging any more. It stays
visible and editable via a manual type edit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7ae608b1233e"
down_revision: str | None = "90e4ebe3930d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RENAME = {"cardigan": "blouson", "jumpsuit": "overall"}


def upgrade() -> None:
    conn = op.get_bind()
    for old, new in _RENAME.items():
        conn.execute(
            sa.text('UPDATE clothing_items SET "type" = :new WHERE "type" = :old'),
            {"new": new, "old": old},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for old, new in _RENAME.items():
        conn.execute(
            sa.text('UPDATE clothing_items SET "type" = :old WHERE "type" = :new'),
            {"old": old, "new": new},
        )
