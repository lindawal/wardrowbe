import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.item import ClothingItem
    from app.models.user import User


class InspirationStatus(enum.StrEnum):
    pending = "pending"
    analyzing = "analyzing"
    analyzed = "analyzed"
    error = "error"


class InspirationLook(Base):
    """An uploaded trend/inspiration photo (Step 1), analyzed item-by-item by AI.

    Deliberately separate from Outfit/photo looks: an InspirationLook is not an
    outfit the user owns or wears, it's a look to draw inspiration from and
    (in Step 2) match against the wardrobe.
    """

    __tablename__ = "inspiration_looks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Image paths follow ImageService's layout, same as outfit photo looks.
    photo_path: Mapped[str] = mapped_column(String(500), nullable=False)
    photo_medium_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    photo_thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[InspirationStatus] = mapped_column(
        Enum(InspirationStatus, name="inspiration_status", create_type=False),
        default=InspirationStatus.pending,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    items: Mapped[list["InspirationLookItem"]] = relationship(
        "InspirationLookItem",
        back_populates="look",
        cascade="all, delete-orphan",
        order_by="InspirationLookItem.position",
    )


class InspirationLookItem(Base):
    """One garment AI identified within an InspirationLook's photo.

    Tag fields mirror ClothingItem's vocabulary (see app/services/ai_service.py's
    VALID_* sets) so the same tag editor / matching logic can work on both.
    """

    __tablename__ = "inspiration_look_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inspiration_look_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inspiration_looks.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Classification
    type: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    subtype: Mapped[str | None] = mapped_column(String(50))

    # Tags and attributes
    primary_color: Mapped[str | None] = mapped_column(String(30))
    colors: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default=text("'{}'")
    )
    pattern: Mapped[str | None] = mapped_column(String(30))
    material: Mapped[str | None] = mapped_column(String(30))
    style: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default=text("'{}'")
    )
    formality: Mapped[str | None] = mapped_column(String(30))
    season: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default=text("'{}'")
    )
    fit: Mapped[str | None] = mapped_column(String(30))

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Step 2 will populate this once matching against the wardrobe is implemented.
    matched_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clothing_items.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    look: Mapped["InspirationLook"] = relationship("InspirationLook", back_populates="items")
    matched_item: Mapped[Optional["ClothingItem"]] = relationship(
        "ClothingItem", foreign_keys=[matched_item_id]
    )
