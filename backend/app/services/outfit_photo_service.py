"""Photo looks: lookbook outfits made from an uploaded photo instead of clothing items.

AI analysis of the stored photo can later be enqueued right after create_photo_look commits,
the same way item uploads enqueue tagging.
"""

import logging
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outfit import Outfit, OutfitSource, OutfitStatus
from app.models.user import User
from app.services.image_service import MAX_IMAGE_BYTES, ImageService, ImageTooLargeError
from app.services.studio_service import load_full_outfit

logger = logging.getLogger(__name__)

MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}
EXTENSION_MIMES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}


class PhotoInvalidError(ValueError):
    pass


class PhotoTooLargeError(ValueError):
    pass


def resolve_photo_mime(content_type: str | None, filename: str | None) -> str | None:
    # Browsers other than Safari often upload HEIC photos without a content type.
    if content_type in MIME_EXTENSIONS:
        return content_type
    return EXTENSION_MIMES.get(Path(filename or "").suffix.lower())


def photo_paths(outfit: Outfit) -> list[str]:
    paths = (outfit.photo_path, outfit.photo_medium_path, outfit.photo_thumbnail_path)
    return [path for path in paths if path]


def delete_photo_files(paths: Iterable[str], image_service: ImageService | None = None) -> None:
    paths = list(paths)
    if not paths:
        return
    try:
        (image_service or ImageService()).delete_images({path: path for path in paths})
    except OSError:
        logger.exception("Failed to delete photo look files %s", paths)


class OutfitPhotoService:
    def __init__(self, db: AsyncSession, image_service: ImageService | None = None):
        self.db = db
        self.image_service = image_service or ImageService()

    async def create_photo_look(
        self,
        user: User,
        image_data: bytes,
        content_type: str | None,
        filename: str | None,
        name: str,
        occasion: str,
        tags: list[str] | None = None,
        seasons: list[str] | None = None,
        weather_tags: list[str] | None = None,
    ) -> Outfit:
        if len(image_data) > MAX_IMAGE_BYTES:
            raise PhotoTooLargeError("photo exceeds the upload size limit")

        mime = resolve_photo_mime(content_type, filename)
        if mime is None or not self.image_service.validate_image(image_data, mime):
            raise PhotoInvalidError("unsupported or unreadable image")

        try:
            stored = await self.image_service.process_and_store(
                user.id, image_data, f"photo{MIME_EXTENSIONS[mime]}"
            )
        except ImageTooLargeError as e:
            raise PhotoTooLargeError(str(e)) from e
        except (ValueError, OSError) as e:
            raise PhotoInvalidError(str(e)) from e

        outfit = Outfit(
            user_id=user.id,
            occasion=occasion,
            scheduled_for=None,
            source=OutfitSource.manual,
            status=OutfitStatus.pending,
            name=name,
            tags=tags or [],
            seasons=seasons or [],
            weather_tags=weather_tags or [],
            photo_path=stored["image_path"],
            photo_medium_path=stored["medium_path"],
            photo_thumbnail_path=stored["thumbnail_path"],
        )
        self.db.add(outfit)

        # Commit here rather than in the request dependency: the files must only survive a
        # successful commit, so a failed one removes them again.
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            delete_photo_files(
                [stored["image_path"], stored["medium_path"], stored["thumbnail_path"]],
                self.image_service,
            )
            raise

        return await load_full_outfit(self.db, outfit.id)
