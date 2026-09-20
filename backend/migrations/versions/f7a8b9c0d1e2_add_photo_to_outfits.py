"""add photo paths to outfits for uploaded photo looks

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-14

A downgrade turns photo looks into empty outfits and leaves their image files on disk.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHOTO_COLUMNS = ("photo_path", "photo_medium_path", "photo_thumbnail_path")


def upgrade() -> None:
    for column in PHOTO_COLUMNS:
        op.add_column("outfits", sa.Column(column, sa.String(length=500), nullable=True))


def downgrade() -> None:
    for column in reversed(PHOTO_COLUMNS):
        op.drop_column("outfits", column)
