"""mark existing "wear today" copies as accepted

Revision ID: c7d41e9a5b30
Revises: 2ee906976596
Create Date: 2026-10-09

StudioService.wear_today() used to create the dated copy of a lookbook template
with status "pending", so a worn outfit showed up under "Offen" instead of
"Getragen". New copies are created as accepted; this fixes the ones already
stored. Downgrade is a no-op: the old status carried no information.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c7d41e9a5b30"
down_revision: str | None = "2ee906976596"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE outfits
        SET status = 'accepted',
            responded_at = COALESCE(responded_at, now())
        WHERE status = 'pending'
          AND source = 'manual'
          AND cloned_from_outfit_id IS NOT NULL
          AND scheduled_for IS NOT NULL
          AND replaces_outfit_id IS NULL
          AND EXISTS (
              SELECT 1 FROM user_feedback f
              WHERE f.outfit_id = outfits.id AND f.worn_at IS NOT NULL
          )
        """
    )


def downgrade() -> None:
    pass
