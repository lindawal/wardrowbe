import asyncio
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from arq import Retry
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.inspiration import InspirationLook, InspirationLookItem, InspirationStatus
from app.services.ai_service import AIService
from app.services.inspiration_matching_service import match_look
from app.workers.db import get_db_session
from app.workers.tagging import _is_final_attempt, _tagging_call_budget, retry_delay_seconds

logger = logging.getLogger(__name__)


class InspirationLookVanishedError(Exception):
    """The look row is not visible to this worker's connection.

    Same reasoning as ItemVanishedError in tagging.py: almost always means the
    producing request has not committed yet, so the job must be retried rather
    than dropped.
    """


async def _mark_error(ctx: dict, look_id: str, error_msg: str) -> None:
    db = get_db_session(ctx)
    try:
        # Guarded so a stale/late write never clobbers a look that has already
        # reached a terminal state (analyzed, or already errored by a later attempt).
        result = await db.execute(select(InspirationLook).where(InspirationLook.id == UUID(look_id)))
        look = result.scalar_one_or_none()
        if look and look.status in (InspirationStatus.pending, InspirationStatus.analyzing):
            look.status = InspirationStatus.error
            look.error_message = error_msg
            await db.commit()
    finally:
        await db.close()


async def _load_look_with_items(db, look_id: str) -> InspirationLook:
    result = await db.execute(
        select(InspirationLook)
        .options(selectinload(InspirationLook.items))
        .where(InspirationLook.id == UUID(look_id))
        .execution_options(populate_existing=True)
    )
    look = result.scalar_one_or_none()
    if look is None:
        raise InspirationLookVanishedError(f"Look {look_id} not visible to worker")
    return look


async def analyze_inspiration_look(ctx: dict, look_id: str, image_path: str) -> dict[str, Any]:
    """Analyze an inspiration look's photo item-by-item and store the results.

    Mirrors tag_item_image's structure (shared call budget, retry-on-transient-error,
    final attempt marks the row errored) but replaces a *list* of InspirationLookItem
    rows rather than updating fields on a single item -- a full re-analysis, not a
    merge.

    Then matches the new items against the wardrobe (Step 2). That runs in its own
    session after the items are committed, and the look only flips to `analyzed`
    once it's done, so the UI never shows an analyzed-but-unmatched look in between.
    A matching failure is logged and leaves the look unmatched (matched_at NULL, the
    UI offers a manual re-match) instead of failing the job -- a retry would redo the
    expensive AI call just to repeat pure database work.
    """
    logger.info(f"Starting AI analysis for inspiration look {look_id}")

    if not get_settings().effective_ai_vision_enabled:
        logger.info(f"Internal vision disabled; skipping analysis for look {look_id}")
        await _mark_error(ctx, look_id, "AI vision is disabled")
        return {"status": "skipped", "reason": "vision disabled", "look_id": look_id}

    try:
        path = Path(image_path)
        if not path.exists():
            error_msg = f"Image not found: {image_path}"
            logger.error(error_msg)
            await _mark_error(ctx, look_id, error_msg)
            return {"status": "error", "error": "Image not found"}

        db = get_db_session(ctx)
        try:
            result = await db.execute(select(InspirationLook).where(InspirationLook.id == UUID(look_id)))
            look = result.scalar_one_or_none()
            if look is None:
                raise InspirationLookVanishedError(f"Look {look_id} not visible to worker")
            look.status = InspirationStatus.analyzing
            look.error_message = None
            await db.commit()
        finally:
            await db.close()

        ai_service = AIService()
        items = await asyncio.wait_for(
            ai_service.analyze_outfit_look(path), timeout=_tagging_call_budget(ai_service)
        )

        logger.info(f"AI analysis complete for look {look_id}: {len(items)} item(s) found")

        db = get_db_session(ctx)
        try:
            result = await db.execute(
                select(InspirationLook)
                .options(selectinload(InspirationLook.items))
                .where(InspirationLook.id == UUID(look_id))
            )
            look = result.scalar_one_or_none()
            if look is None:
                raise InspirationLookVanishedError(f"Look {look_id} not visible to worker")

            for existing in list(look.items):
                await db.delete(existing)

            for position, tags in enumerate(items):
                db.add(
                    InspirationLookItem(
                        inspiration_look_id=look.id,
                        position=position,
                        type=tags.type,
                        subtype=tags.subtype,
                        primary_color=tags.primary_color,
                        colors=tags.colors,
                        pattern=tags.pattern,
                        material=tags.material,
                        style=tags.style,
                        formality=tags.formality,
                        season=tags.season,
                        fit=tags.fit,
                        description=tags.description,
                        confidence=tags.confidence,
                    )
                )

            # Status stays `analyzing` until matching below has run.
            look.matched_at = None
            await db.commit()
            logger.info(f"Stored {len(items)} item(s) for look {look_id}")
        finally:
            await db.close()

        db = get_db_session(ctx)
        try:
            look = await _load_look_with_items(db, look_id)
            matched = True
            try:
                await match_look(db, look)
            except Exception:
                matched = False
                logger.exception(
                    f"Wardrobe matching failed for inspiration look {look_id}; leaving it unmatched"
                )
                await db.rollback()
                look = await _load_look_with_items(db, look_id)

            look.status = InspirationStatus.analyzed
            look.error_message = None
            await db.commit()

            return {
                "status": "success",
                "look_id": look_id,
                "item_count": len(items),
                "matched": matched,
            }
        finally:
            await db.close()

    except asyncio.CancelledError:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.exception(f"Error analyzing inspiration look {look_id}: {error_msg}")
        # Returning normally here would make max_tries dead: arq books a returned
        # value as success, so a real failure has to re-raise or Retry to be seen.
        if _is_final_attempt(ctx):
            await _mark_error(ctx, look_id, error_msg)
            raise
        raise Retry(defer=retry_delay_seconds(ctx)) from e
