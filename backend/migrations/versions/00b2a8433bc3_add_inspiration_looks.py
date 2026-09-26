"""add inspiration_looks and inspiration_look_items (Step 1: upload + AI analysis)

Revision ID: 00b2a8433bc3
Revises: 944622316e48
Create Date: 2026-09-27

An inspiration look is a photo of a trend/outfit found elsewhere (e.g. an online
shop) that the user uploads to have identified item-by-item by AI, then corrects
by hand. inspiration_look_items stores one row per detected garment, using the
same tag vocabulary as clothing_items (validated at the app layer in
app/services/ai_service.py, not via DB constraints -- same choice made there).

matched_item_id is added now but stays unused until Step 2 (matching against the
user's own wardrobe); it is nullable and SET NULL on delete so removing a wardrobe
item never cascades into deleting an inspiration look.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ARRAY, UUID

# revision identifiers, used by Alembic.
revision: str = "00b2a8433bc3"
down_revision: str | None = "944622316e48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE inspiration_status AS ENUM ('pending', 'analyzing', 'analyzed', 'error')"
    )

    op.create_table(
        "inspiration_looks",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("photo_path", sa.String(500), nullable=False),
        sa.Column("photo_medium_path", sa.String(500), nullable=True),
        sa.Column("photo_thumbnail_path", sa.String(500), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "analyzing",
                "analyzed",
                "error",
                name="inspiration_status",
                create_type=False,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_inspiration_looks_user_id", "inspiration_looks", ["user_id"])

    op.create_table(
        "inspiration_look_items",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "inspiration_look_id",
            UUID(as_uuid=True),
            sa.ForeignKey("inspiration_looks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("type", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("subtype", sa.String(50), nullable=True),
        sa.Column("primary_color", sa.String(30), nullable=True),
        sa.Column("colors", ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("pattern", sa.String(30), nullable=True),
        sa.Column("material", sa.String(30), nullable=True),
        sa.Column("style", ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("formality", sa.String(30), nullable=True),
        sa.Column("season", ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("fit", sa.String(30), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column(
            "matched_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clothing_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_inspiration_look_items_look_id", "inspiration_look_items", ["inspiration_look_id"]
    )
    op.create_index(
        "ix_inspiration_look_items_matched_item_id", "inspiration_look_items", ["matched_item_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inspiration_look_items_matched_item_id", table_name="inspiration_look_items"
    )
    op.drop_index("ix_inspiration_look_items_look_id", table_name="inspiration_look_items")
    op.drop_table("inspiration_look_items")

    op.drop_index("ix_inspiration_looks_user_id", table_name="inspiration_looks")
    op.drop_table("inspiration_looks")

    op.execute("DROP TYPE IF EXISTS inspiration_status")
