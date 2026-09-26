"""API for Step 1 (inspiration looks): upload a trend/outfit photo, have AI break it
down item-by-item, and let the user correct the tags by hand. Step 2 (matching these
against the wardrobe) builds on top of this.
"""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from arq import create_pool
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.inspiration import InspirationLook, InspirationLookItem, InspirationStatus
from app.models.user import User
from app.schemas.inspiration import InspirationLookItemUpdate
from app.services.inspiration_service import (
    InspirationLookItemNotFoundError,
    InspirationService,
)
from app.services.outfit_photo_service import PhotoInvalidError, PhotoTooLargeError
from app.utils.auth import get_current_user
from app.utils.rate_limit import rate_limit_by_user
from app.utils.signed_urls import sign_image_url
from app.workers.queues import TAGGING_QUEUE
from app.workers.settings import get_redis_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspiration", tags=["Inspiration"])


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


class InspirationLookResponse(BaseModel):
    id: UUID
    status: InspirationStatus
    error_message: str | None = None
    photo_url: str | None = None
    photo_medium_url: str | None = None
    photo_thumbnail_url: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[InspirationLookItemResponse] = []


class InspirationLookListResponse(BaseModel):
    looks: list[InspirationLookResponse]


def item_to_response(item: InspirationLookItem) -> InspirationLookItemResponse:
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
    )


def look_to_response(look: InspirationLook) -> InspirationLookResponse:
    return InspirationLookResponse(
        id=look.id,
        status=look.status,
        error_message=look.error_message,
        photo_url=sign_image_url(look.photo_path) if look.photo_path else None,
        photo_medium_url=sign_image_url(look.photo_medium_path) if look.photo_medium_path else None,
        photo_thumbnail_url=sign_image_url(look.photo_thumbnail_path)
        if look.photo_thumbnail_path
        else None,
        created_at=look.created_at,
        updated_at=look.updated_at,
        items=[item_to_response(i) for i in sorted(look.items, key=lambda i: i.position)],
    )


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
    # this fails the look just stays `pending` -- there's no retry endpoint yet in
    # Step 1, so the user would need to re-upload (an accepted, disclosed gap).
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
    return InspirationLookListResponse(looks=[look_to_response(look) for look in looks])


@router.get("/{look_id}", response_model=InspirationLookResponse)
async def get_inspiration_look(
    look_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InspirationLookResponse:
    service = InspirationService(db)
    look = await service.get_look(look_id, current_user.id)
    if look is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "INSPIRATION_LOOK_NOT_FOUND",
                "message": "Inspiration look not found",
            },
        )
    return look_to_response(look)


@router.patch("/{look_id}/items/{item_id}", response_model=InspirationLookItemResponse)
async def update_inspiration_look_item(
    look_id: UUID,
    item_id: UUID,
    request: InspirationLookItemUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InspirationLookItemResponse:
    service = InspirationService(db)
    look = await service.get_look(look_id, current_user.id)
    if look is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "INSPIRATION_LOOK_NOT_FOUND",
                "message": "Inspiration look not found",
            },
        )

    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "NO_FIELDS", "message": "No fields to update"},
        )

    try:
        item = await service.update_item(look, item_id, updates)
    except InspirationLookItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "INSPIRATION_ITEM_NOT_FOUND", "message": "Item not found"},
        ) from None

    return item_to_response(item)


@router.delete("/{look_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inspiration_look(
    look_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    service = InspirationService(db)
    look = await service.get_look(look_id, current_user.id)
    if look is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "INSPIRATION_LOOK_NOT_FOUND",
                "message": "Inspiration look not found",
            },
        )
    await service.delete_look(look)
