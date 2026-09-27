"""Inspiration looks: an uploaded trend/outfit photo, analyzed item-by-item by AI
(Step 1) and matched against the user's own wardrobe so it can be restyled from it
(Step 2).

Deliberately separate from OutfitPhotoService/photo looks: an InspirationLook is not
an outfit the user owns or wears, it's a look to draw inspiration from. Image storage
and MIME handling reuse the exact same helpers as photo looks / worn photos.
"""

import logging
from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inspiration import InspirationLook, InspirationLookItem, InspirationStatus
from app.models.item import ClothingItem, ItemStatus
from app.models.outfit import Outfit
from app.models.user import User
from app.services.external_outfit_service import ExternalOutfitService
from app.services.image_service import MAX_IMAGE_BYTES, ImageService, ImageTooLargeError
from app.services.inspiration_matching_service import (
    MATCH_RELEVANT_FIELDS,
    match_look,
    rematch_item,
)
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


def wardrobe_ids_for_items(items: Iterable[InspirationLookItem]) -> set[UUID]:
    ids: set[UUID] = set()
    for item in items:
        if item.matched_item_id is not None:
            ids.add(item.matched_item_id)
        ids.update(item.suggested_item_ids or [])
    return ids


class InspirationLookItemNotFoundError(LookupError):
    pass


class WardrobeItemUnavailableError(LookupError):
    """The wardrobe item doesn't exist, isn't the user's, or isn't usable (archived,
    still processing, errored) -- the same set validate_item_ownership rejects."""


class InspirationLookNotAnalyzedError(Exception):
    pass


class NoItemsSelectedError(Exception):
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

    async def get_look(
        self, look_id: UUID, user_id: UUID, *, refresh: bool = False
    ) -> InspirationLook | None:
        query = (
            select(InspirationLook)
            .options(selectinload(InspirationLook.items))
            .where(InspirationLook.id == look_id, InspirationLook.user_id == user_id)
        )
        if refresh:
            # Re-read rows (and the items collection) this session already holds.
            query = query.execution_options(populate_existing=True)
        result = await self.db.execute(query)
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

    async def get_usable_wardrobe_items(
        self, user_id: UUID, item_ids: Iterable[UUID]
    ) -> dict[UUID, ClothingItem]:
        """The subset of item_ids the user can actually wear: their own, ready and not
        archived. Anything matched or suggested earlier but gone since drops out here."""
        ids = set(item_ids)
        if not ids:
            return {}
        result = await self.db.execute(
            select(ClothingItem).where(
                and_(
                    ClothingItem.id.in_(ids),
                    ClothingItem.user_id == user_id,
                    ClothingItem.status == ItemStatus.ready,
                    ClothingItem.is_archived.is_(False),
                )
            )
        )
        return {item.id: item for item in result.scalars().all()}

    def _find_item(self, look: InspirationLook, item_id: UUID) -> InspirationLookItem:
        item = next((i for i in look.items if i.id == item_id), None)
        if item is None:
            raise InspirationLookItemNotFoundError(str(item_id))
        return item

    async def update_item(
        self, look: InspirationLook, item_id: UUID, updates: dict
    ) -> InspirationLookItem:
        """Apply a manual correction to one item. `updates` is expected to already be
        validated (InspirationLookItemUpdate.model_dump(exclude_unset=True)) --
        this method trusts its keys/values and just assigns them.

        Actually changing a tag the match depends on re-matches that item, replacing
        its suggestions and any manual pick: the old ones were chosen for the wrong
        tags. "Actually changing" matters because the tag editor always sends the whole
        tag set -- re-sending an unchanged color must not throw away a manual pick.
        Looks that were never matched stay that way until matched explicitly.
        """
        item = self._find_item(look, item_id)

        changed = {field for field, value in updates.items() if getattr(item, field) != value}
        for field, value in updates.items():
            setattr(item, field, value)

        if look.matched_at is not None and MATCH_RELEVANT_FIELDS & changed:
            await rematch_item(self.db, look, item)

        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def add_item(self, look: InspirationLook, fields: dict) -> InspirationLookItem:
        """Add a piece by hand -- one the AI missed. `fields` is expected to already be
        validated (InspirationLookItemCreate.model_dump(exclude_unset=True)).

        Only on analyzed looks: a running analysis replaces all items when it lands.
        The new piece goes last and, if the look has been matched, is matched right
        away like the AI-found ones.
        """
        if look.status != InspirationStatus.analyzed:
            raise InspirationLookNotAnalyzedError(str(look.id))

        position = max((i.position for i in look.items), default=-1) + 1
        item = InspirationLookItem(position=position, **fields)
        look.items.append(item)
        await self.db.flush()

        if look.matched_at is not None:
            await rematch_item(self.db, look, item)

        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def delete_item(self, look: InspirationLook, item_id: UUID) -> None:
        """Remove a piece, e.g. one the AI saw that isn't actually in the photo."""
        item = self._find_item(look, item_id)
        look.items.remove(item)  # delete-orphan cascade deletes the row
        await self.db.commit()

    async def set_match(
        self, look: InspirationLook, item_id: UUID, wardrobe_item_id: UUID | None
    ) -> InspirationLookItem:
        """Pick (or clear, with None) the wardrobe item for one slot. Any usable item
        of the user's is allowed, not only the suggested ones."""
        item = self._find_item(look, item_id)

        if wardrobe_item_id is not None:
            usable = await self.get_usable_wardrobe_items(look.user_id, [wardrobe_item_id])
            if wardrobe_item_id not in usable:
                raise WardrobeItemUnavailableError(str(wardrobe_item_id))

        item.matched_item_id = wardrobe_item_id
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def rematch_look(self, look: InspirationLook) -> InspirationLook:
        """Match the whole look against the wardrobe as it is now; resets manual picks."""
        if look.status != InspirationStatus.analyzed:
            raise InspirationLookNotAnalyzedError(str(look.id))
        await match_look(self.db, look)
        await self.db.commit()
        # Just committed in this session, so the re-read always finds it.
        refreshed = await self.get_look(look.id, look.user_id, refresh=True)
        return refreshed if refreshed is not None else look

    async def recreate_outfit(
        self, look: InspirationLook, user: User, *, occasion: str, name: str | None = None
    ) -> Outfit:
        """Turn the current picks into a regular (external, pending) outfit.

        Slots without a pick -- or whose pick has since been archived/deleted -- are
        left out; the same wardrobe item picked for two slots is used once. Does not
        commit (same contract as ExternalOutfitService).
        """
        if look.status != InspirationStatus.analyzed:
            raise InspirationLookNotAnalyzedError(str(look.id))

        picked = [
            i.matched_item_id
            for i in sorted(look.items, key=lambda i: i.position)
            if i.matched_item_id is not None
        ]
        usable = await self.get_usable_wardrobe_items(user.id, picked)
        item_ids = list(dict.fromkeys(iid for iid in picked if iid in usable))
        if not item_ids:
            raise NoItemsSelectedError(str(look.id))

        outfit = await ExternalOutfitService(self.db).create_suggestion(
            user, item_ids=item_ids, occasion=occasion, name=name
        )
        outfit.inspiration_look_id = look.id
        await self.db.flush()
        return outfit
