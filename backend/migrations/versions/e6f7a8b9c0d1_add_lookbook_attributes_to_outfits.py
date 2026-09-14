"""add lookbook tags, seasons and weather tags to outfits

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LOOKBOOK_COLUMNS = ("tags", "seasons", "weather_tags")


def upgrade() -> None:
    for column in LOOKBOOK_COLUMNS:
        op.add_column(
            "outfits",
            sa.Column(
                column,
                postgresql.ARRAY(sa.String()),
                nullable=False,
                server_default=sa.text("'{}'"),
            ),
        )


def downgrade() -> None:
    for column in reversed(LOOKBOOK_COLUMNS):
        op.drop_column("outfits", column)
