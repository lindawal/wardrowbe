"""API for inspiration looks: upload a trend/outfit photo, have AI break it down
item-by-item and let the user correct the tags by hand (Step 1); match the items
against the wardrobe, let the user swap picks, and restyle the look as a regular
outfit (Step 2).
"""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from arq import create_pool
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.outfits import VALID_OCCASIONS, OutfitResponse, outfit_to_response
from app.config import get_settings
from app.database import get_db
from app.models.inspiration import InspirationLook, InspirationLookItem, InspirationStatus
from app.models.item import ClothingItem
from app.models.user import User
from app.schemas.inspiration import InspirationLookItemUpdate
from app.services.inspiration_service import (
    InspirationLookItemNotFoundError,
    InspirationLookNotAnalyzedError,
    InspirationService,
    NoItemsSelectedError,
    WardrobeItemUnavailableError,
    wardrobe_ids_for_items,
)
from app.services.outfit_photo_service import PhotoInvalidError, PhotoTooLargeError
from app.services.studio_service import ItemOwnershipError, load_full_outfit
from app.services.suggestion_cache import clear_suggestions
from app.utils.auth import get_current_user
from app.utils.rate_limit import rate_limit_by_user
from app.utils.signed_urls import sign_image_url
from app.workers.queues import TAGGING_QUEUE
from app.workers.settings import get_redis_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspiration", tags=["Inspiration"])

WardrobeMap = dict[UUID, ClothingItem]


class WardrobeItemSummary(BaseModel):
    """Just enough of a wardrobe item to show it as a match."""

    id: UUID
    type: str
    subtype: str | None = None
    name: str | None = None
    primary_color: str | None = None
    image_url: str | None = None
    thumbnail_url: str | None = None


class InspirationLookItemResponse(BaseModel):
    id: UUID
    position: int
    type: str
    subtype: str | None = None
    primary_color: str | None = None
    colors: list[str] = []
    pattern: str | None = None
    material: str | None = None
    style: list[str] = []
    formality: str | None = None
    season: list[str] = []
    fit: str | None = None
    description: str | None = None
    confidence: float | None = None
    matched_item_id: UUID | None = None
    # Resolved wardrobe items (Step 2). matched_item is None when nothing is picked
    # or the pick is no longer usable (archived/deleted); suggested_items is in rank
    # order and already drops unusable ids. Both stay empty in list responses.
    matched_item: WardrobeItemSummary | None = None
    suggested_items: list[WardrobeItemSummary] = []


class InspirationLookResponse(BaseModel):
    id: UUID
    status: InspirationStatus
    error_message: str | None = None
    photo_url: str | None = None
    photo_medium_url: str | None = None
    photo_thumbnail_url: str | None = None
    matched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[InspirationLookItemResponse] = []


class InspirationLookListResponse(BaseModel):
    looks: list[InspirationLookResponse]


class InspirationMatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None clears the slot ("leave this piece out").
    wardrobe_item_id: UUID | None


class InspirationRecreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    occasion: str = Field(max_length=50)
    name: Annotated[str | None, Field(max_length=100)] = None

    @field_validator("occasion")
    @classmethod
    def validate_occasion(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_OCCASIONS:
            raise ValueError(
                f"Invalid occasion '{v}'. Must be one of: {', '.join(sorted(VALID_OCCASIONS))}"
            )
        return v

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip() or None


def wardrobe_item_summary(item: ClothingItem) -> WardrobeItemSummary:
    return WardrobeItemSummary(
        id=item.id,
        type=item.type,
        subtype=item.subtype,
        name=item.name,
        primary_color=item.primary_color,
        image_url=sign_image_url(item.image_path) if item.image_path else None,
        thumbnail_url=sign_image_url(item.thumbnail_path) if item.thumbnail_path else None,
    )


def item_to_response(
    item: InspirationLookItem, wardrobe: WardrobeMap | None = None
) -> InspirationLookItemResponse:
    matched_item = None
    suggested_items: list[WardrobeItemSummary] = []
    if wardrobe is not None:
        if item.matched_item_id is not None and item.matched_item_id in wardrobe:
            matched_item = wardrobe_item_summary(wardrobe[item.matched_item_id])
        suggested_items = [
            wardrobe_item_summary(wardrobe[iid])
            for iid in (item.suggested_item_ids or [])
            if iid in wardrobe
        ]

    return InspirationLookItemResponse(
        id=item.id,
        position=item.position,
        type=item.type,
        subtype=item.subtype,
        primary_color=item.primary_color,
        colors=item.colors,
        pattern=item.pattern,
        material=item.material,
        style=item.style,
        formality=item.formality,
        season=item.season,
        fit=item.fit,
        description=item.description,
        confidence=item.confidence,
        matched_item_id=item.matched_item_id,
        matched_item=matched_item,
        suggested_items=suggested_items,
    )


def look_to_response(
    look: InspirationLook, wardrobe: WardrobeMap | None = None
) -> InspirationLookResponse:
    return InspirationLookResponse(
        id=look.id,
        status=look.status,
        error_message=look.error_message,
        photo_url=sign_image_url(look.photo_path) if look.photo_path else None,
        photo_medium_url=sign_image_url(look.photo_medium_path) if look.photo_medium_path else None,
        photo_thumbnail_url=sign_image_url(look.photo_thumbnail_path)
        if look.photo_thumbnail_path
        else None,
        matched_at=look.matched_at,
        created_at=look.created_at,
        updated_at=look.updated_at,
        items=[
            item_to_response(i, wardrobe) for i in sorted(look.items, key=lambda i: i.position)
        ],
    )


async def _resolved_look_response(
    service: InspirationService, look: InspirationLook
) -> InspirationLookResponse:
    wardrobe = await service.get_usable_wardrobe_items(
        look.user_id, wardrobe_ids_for_items(look.items)
    )
    return look_to_response(look, wardrobe)


async def _resolved_item_response(
    service: InspirationService, look: InspirationLook, item: InspirationLookItem
) -> InspirationLookItemResponse:
    wardrobe = await service.get_usable_wardrobe_items(look.user_id, wardrobe_ids_for_items([item]))
    return item_to_response(item, wardrobe)


def _look_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error_code": "INSPIRATION_LOOK_NOT_FOUND",
            "message": "Inspiration look not found",
        },
    )


def _item_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "INSPIRATION_ITEM_NOT_FOUND", "message": "Item not found"},
    )


def _not_analyzed() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error_code": "INSPIRATION_LOOK_NOT_ANALYZED",
            "message": "The look has not been analyzed yet",
        },
    )


async def _get_look_or_404(
    service: InspirationService, look_id: UUID, user_id: UUID
) -> InspirationLook:
    look = await service.get_look(look_id, user_id)
    if look is None:
        raise _look_not_found()
    return look


@router.post("", response_model=InspirationLookResponse, status_code=status.HTTP_201_CREATED)
async def upload_inspiration_look(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    image: UploadFile = File(...),
) -> InspirationLookResponse:
    settings = get_settings()
    if not settings.effective_ai_vision_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "AI_VISION_DISABLED",
                "message": "AI-based analysis is disabled; inspiration looks require it.",
            },
        )
    await rate_limit_by_user(
        str(current_user.id), "inspiration_upload", max_requests=10, window_seconds=60
    )

    service = InspirationService(db)
    try:
        look = await service.create_look(
            user=current_user,
            image_data=await image.read(),
            content_type=image.content_type,
            filename=image.filename,
        )
    except PhotoTooLargeError:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error_code": "PHOTO_TOO_LARGE", "message": "Photo is too large"},
        ) from None
    except PhotoInvalidError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "PHOTO_INVALID",
                "message": "Invalid image file. Supported formats: JPEG, PNG, WebP, HEIC",
            },
        ) from None

    # Commit already happened inside create_look; enqueue the analysis job next. If
    # this fails the look just stays `pending` -- there's no retry endpoint for the
    # analysis, so the user would need to re-upload (an accepted, disclosed gap).
    try:
        redis = await create_pool(get_redis_settings())
        try:
            full_image_path = f"{settings.storage_path}/{look.photo_path}"
            await redis.enqueue_job(
                "analyze_inspiration_look",
                str(look.id),
                full_image_path,
                _queue_name=TAGGING_QUEUE,
            )
            logger.info(f"Queued inspiration analysis job for look {look.id}")
        finally:
            await redis.aclose()
    except Exception as e:
        logger.error(f"Failed to queue inspiration analysis job for look {look.id}: {e}")

    return look_to_response(look)


@router.get("", response_model=InspirationLookListResponse)
async def list_inspiration_looks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> InspirationLookListResponse:
    service = InspirationService(db)
    looks = await service.list_looks(current_user.id, limit=limit, offset=offset)
    # Matches aren't resolved here: the list only shows thumbnails and status.
    return InspirationLookListResponse(looks=[look_to_response(look) for look in looks])


@router.get("/{look_id}", response_model=InspirationLookResponse)
async def get_inspiration_look(
    look_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InspirationLookResponse:
    service = InspirationService(db)
    look = await _get_look_or_404(service, look_id, current_user.id)
    return await _resolved_look_response(service, look)


@router.patch("/{look_id}/items/{item_id}", response_model=InspirationLookItemResponse)
async def update_inspiration_look_item(
    look_id: UUID,
    item_id: UUID,
    request: InspirationLookItemUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InspirationLookItemResponse:
    service = InspirationService(db)
    look = await _get_look_or_404(service, look_id, current_user.id)

    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "NO_FIELDS", "message": "No fields to update"},
        )

    try:
        item = await service.update_item(look, item_id, updates)
    except InspirationLookItemNotFoundError:
        raise _item_not_found() from None

    return await _resolved_item_response(service, look, item)


@router.patch("/{look_id}/items/{item_id}/match", response_model=InspirationLookItemResponse)
async def set_inspiration_look_item_match(
    look_id: UUID,
    item_id: UUID,
    request: InspirationMatchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InspirationLookItemResponse:
    """Swap the wardrobe item picked for one slot, or clear it with null."""
    service = InspirationService(db)
    look = await _get_look_or_404(service, look_id, current_user.id)

    try:
        item = await service.set_match(look, item_id, request.wardrobe_item_id)
    except InspirationLookItemNotFoundError:
        raise _item_not_found() from None
    except WardrobeItemUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "WARDROBE_ITEM_NOT_FOUND",
                "message": "Wardrobe item not found or not usable",
            },
        ) from None

    return await _resolved_item_response(service, look, item)


@router.post("/{look_id}/match", response_model=InspirationLookResponse)
async def rematch_inspiration_look(
    look_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InspirationLookResponse:
    """Match the look against the wardrobe as it is now (e.g. after adding items).
    Replaces all suggestions and resets manual picks."""
    await rate_limit_by_user(
        str(current_user.id), "inspiration_match", max_requests=20, window_seconds=60
    )
    service = InspirationService(db)
    look = await _get_look_or_404(service, look_id, current_user.id)

    try:
        look = await service.rematch_look(look)
    except InspirationLookNotAnalyzedError:
        raise _not_analyzed() from None

    return await _resolved_look_response(service, look)


@router.post(
    "/{look_id}/recreate", response_model=OutfitResponse, status_code=status.HTTP_201_CREATED
)
async def recreate_inspiration_look(
    look_id: UUID,
    request: InspirationRecreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OutfitResponse:
    """Create a regular outfit from the current picks. It lands like any authored
    suggestion (source=external, pending, today), so the usual accept/skip/reject
    buttons apply, and carries inspiration_look_id back to this look."""
    await rate_limit_by_user(
        str(current_user.id), "inspiration_recreate", max_requests=20, window_seconds=60
    )
    service = InspirationService(db)
    look = await _get_look_or_404(service, look_id, current_user.id)

    try:
        outfit = await service.recreate_outfit(
            look, current_user, occasion=request.occasion, name=request.name
        )
    except InspirationLookNotAnalyzedError:
        raise _not_analyzed() from None
    except NoItemsSelectedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "NO_ITEMS_SELECTED",
                "message": "Pick at least one wardrobe item before restyling the look",
            },
        ) from None
    except ItemOwnershipError:
        # A pick became unusable between the check and the insert.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "WARDROBE_CHANGED",
                "message": "One of the picked items is no longer available",
            },
        ) from None

    await db.commit()
    # Same as the external-suggestion endpoint: a new pending outfit for today makes
    # the cached suggestions for this occasion stale.
    await clear_suggestions(current_user.id, request.occasion)

    full = await load_full_outfit(db, outfit.id)
    return outfit_to_response(full)


@router.delete("/{look_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inspiration_look(
    look_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    service = InspirationService(db)
    look = await _get_look_or_404(service, look_id, current_user.id)
    await service.delete_look(look)
