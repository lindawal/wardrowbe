"""Inspiration looks (Step 1): an uploaded trend/outfit photo, analyzed item-by-item
by AI so it can later (Step 2) be restyled from the user's own wardrobe.

Deliberately separate from OutfitPhotoService/photo looks: an InspirationLook is not
an outfit the user owns or wears, it's a look to draw inspiration from. Image storage
and MIME handling reuse the exact same helpers as photo looks / worn photos.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inspiration import InspirationLook, InspirationLookItem, InspirationStatus
from app.models.user import User
from app.services.image_service import MAX_IMAGE_BYTES, ImageService, ImageTooLargeError
from app.services.outfit_photo_service import (
    MIME_EXTENSIONS,
    PhotoInvalidError,
    PhotoTooLargeError,
    delete_photo_files,
    resolve_photo_mime,
)

logger = logging.getLogger(__name__)


def look_photo_paths(look: InspirationLook) -> list[str]:
    paths = (look.photo_path, look.photo_medium_path, look.photo_thumbnail_path)
    return [path for path in paths if path]


class InspirationLookItemNotFoundError(LookupError):
    pass


class InspirationService:
    def __init__(self, db: AsyncSession, image_service: ImageService | None = None):
        self.db = db
        self.image_service = image_service or ImageService()

    async def create_look(
        self,
        user: User,
        image_data: bytes,
        content_type: str | None,
        filename: str | None,
    ) -> InspirationLook:
        if len(image_data) > MAX_IMAGE_BYTES:
            raise PhotoTooLargeError("photo exceeds the upload size limit")

        mime = resolve_photo_mime(content_type, filename)
        if mime is None or not self.image_service.validate_image(image_data, mime):
            raise PhotoInvalidError("unsupported or unreadable image")

        try:
            stored = await self.image_service.process_and_store(
                user.id, image_data, f"inspiration{MIME_EXTENSIONS[mime]}"
            )
        except ImageTooLargeError as e:
            raise PhotoTooLargeError(str(e)) from e
        except (ValueError, OSError) as e:
            raise PhotoInvalidError(str(e)) from e

        look = InspirationLook(
            user_id=user.id,
            photo_path=stored["image_path"],
            photo_medium_path=stored["medium_path"],
            photo_thumbnail_path=stored["thumbnail_path"],
            status=InspirationStatus.pending,
        )
        self.db.add(look)

        # Commit here rather than in the request dependency: the files must only
        # survive a successful commit, so a failed one removes them again (same
        # pattern as OutfitPhotoService.create_photo_look).
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            delete_photo_files(
                [stored["image_path"], stored["medium_path"], stored["thumbnail_path"]],
                self.image_service,
            )
            raise

        # Re-fetch with items eager-loaded, same pattern as create_photo_look's
        # load_full_outfit -- freshly created, so this is always a hit.
        return await self.get_look(look.id, user.id)

    async def get_look(self, look_id: UUID, user_id: UUID) -> InspirationLook | None:
        result = await self.db.execute(
            select(InspirationLook)
            .options(selectinload(InspirationLook.items))
            .where(InspirationLook.id == look_id, InspirationLook.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_looks(
        self, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[InspirationLook]:
        result = await self.db.execute(
            select(InspirationLook)
            .options(selectinload(InspirationLook.items))
            .where(InspirationLook.user_id == user_id)
            .order_by(InspirationLook.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def delete_look(self, look: InspirationLook) -> None:
        paths = look_photo_paths(look)
        await self.db.delete(look)
        await self.db.commit()
        # Photo files go only once the row is gone for good.
        delete_photo_files(paths, self.image_service)

    async def update_item(
        self, look: InspirationLook, item_id: UUID, updates: dict
    ) -> InspirationLookItem:
        """Apply a manual correction to one item. `updates` is expected to already be
        validated (InspirationLookItemUpdate.model_dump(exclude_unset=True)) --
        this method trusts its keys/values and just assigns them.
        """
        item = next((i for i in look.items if i.id == item_id), None)
        if item is None:
            raise InspirationLookItemNotFoundError(str(item_id))

        for field, value in updates.items():
            setattr(item, field, value)

        await self.db.commit()
        await self.db.refresh(item)
        return item
