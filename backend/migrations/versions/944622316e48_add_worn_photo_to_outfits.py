"""add worn photo paths to outfits for restyled/manual outfits

Revision ID: 944622316e48
Revises: a76a529ec612
Create Date: 2026-09-26

Separate from photo_path/photo_medium_path/photo_thumbnail_path (which define
is_photo_look -- an outfit that IS a photo instead of a set of items). These
new columns let a regular, item-based outfit additionally carry a photo of the
look actually being worn, without touching the is_photo_look invariant that
many call sites (studio_service.OutfitIsPhotoLookError and friends) rely on.

A downgrade drops the columns and leaves any stored worn-photo files on disk,
same choice as f7a8b9c0d1e2 made for photo looks.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "944622316e48"
down_revision: str | None = "a76a529ec612"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORN_PHOTO_COLUMNS = ("worn_photo_path", "worn_photo_medium_path", "worn_photo_thumbnail_path")


def upgrade() -> None:
    for column in WORN_PHOTO_COLUMNS:
        op.add_column("outfits", sa.Column(column, sa.String(length=500), nullable=True))


def downgrade() -> None:
    for column in reversed(WORN_PHOTO_COLUMNS):
        op.drop_column("outfits", column)
