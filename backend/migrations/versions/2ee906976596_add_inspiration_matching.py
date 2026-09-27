"""add wardrobe matching to inspiration looks (Step 2)

Revision ID: 2ee906976596
Revises: 00b2a8433bc3
Create Date: 2026-09-27

Step 2 matches every analyzed inspiration item against the user's wardrobe once,
inside the analysis job (Linda's decision), and stores the result:

- inspiration_look_items.suggested_item_ids: the best wardrobe candidates in rank
  order (best match + 2 alternatives). A plain UUID array rather than a join table:
  it is only ever read and rewritten as a whole, and stale ids (items deleted or
  archived since) are filtered out at read time.
- inspiration_look_items.matched_item_id (already added in 00b2a8433bc3) now holds
  the user's current pick, initially suggested_item_ids[0].
- inspiration_looks.matched_at: when matching last ran, so "never matched" (looks
  analyzed before this migration) is distinguishable from "matched, nothing fits".
- outfits.inspiration_look_id: back-reference from an outfit restyled from a look.
  SET NULL on delete so deleting an inspiration look never deletes an outfit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

# revision identifiers, used by Alembic.
revision: str = "2ee906976596"
down_revision: str | None = "00b2a8433bc3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inspiration_look_items",
        sa.Column(
            "suggested_item_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "inspiration_looks",
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outfits",
        sa.Column(
            "inspiration_look_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "inspiration_looks.id",
                ondelete="SET NULL",
                name="fk_outfits_inspiration_look_id",
            ),
            nullable=True,
        ),
    )
    op.create_index("ix_outfits_inspiration_look_id", "outfits", ["inspiration_look_id"])


def downgrade() -> None:
    op.drop_index("ix_outfits_inspiration_look_id", table_name="outfits")
    op.drop_constraint("fk_outfits_inspiration_look_id", "outfits", type_="foreignkey")
    op.drop_column("outfits", "inspiration_look_id")
    op.drop_column("inspiration_looks", "matched_at")
    op.drop_column("inspiration_look_items", "suggested_item_ids")
