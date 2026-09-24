from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import ClothingItem, ItemStatus
from app.services.ai_service import ClothingTags
from app.workers import tagging

AI_TAGS = {
    "colors": ["navy", "white"],
    "pattern": "striped",
    "material": "wool",
    "style": ["classic"],
    "season": ["fall", "winter"],
    "formality": "casual",
    "fit": "slim",
}


async def _tagged_item(db_session: AsyncSession, user_id) -> ClothingItem:
    """An item as the AI tagger leaves it: columns and the tags JSON agree."""
    item = ClothingItem(
        user_id=user_id,
        type="jacket",
        image_path="test/tag-edit.jpg",
        status=ItemStatus.ready,
        primary_color="navy",
        colors=AI_TAGS["colors"],
        pattern=AI_TAGS["pattern"],
        material=AI_TAGS["material"],
        style=AI_TAGS["style"],
        season=AI_TAGS["season"],
        formality=AI_TAGS["formality"],
        tags=dict(AI_TAGS),
    )
    db_session.add(item)
    await db_session.commit()
    return item


class TestTagEditing:
    @pytest.mark.asyncio
    async def test_editing_one_tag_keeps_the_others(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        item = await _tagged_item(db_session, test_user.id)

        response = await client.patch(
            f"/api/v1/items/{item.id}",
            json={"tags": {"formality": "business-casual"}},
            headers=auth_headers,
        )

        assert response.status_code == 200, response.json()
        data = response.json()
        # The detail view reads the tags JSON; scoring reads the columns. Both must
        # carry the edit, and neither may lose the tags that were not sent.
        assert data["tags"] == {**AI_TAGS, "formality": "business-casual"}
        assert data["formality"] == "business-casual"
        assert data["colors"] == AI_TAGS["colors"]
        assert data["style"] == AI_TAGS["style"]
        assert data["season"] == AI_TAGS["season"]
        assert data["pattern"] == AI_TAGS["pattern"]
        assert data["material"] == AI_TAGS["material"]

    @pytest.mark.asyncio
    async def test_optional_tag_can_be_cleared(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        item = await _tagged_item(db_session, test_user.id)

        response = await client.patch(
            f"/api/v1/items/{item.id}",
            json={"tags": {"material": None, "fit": None}},
            headers=auth_headers,
        )

        assert response.status_code == 200, response.json()
        data = response.json()
        assert data["material"] is None
        assert data["tags"]["material"] is None
        assert data["tags"]["fit"] is None
        assert data["tags"]["pattern"] == AI_TAGS["pattern"]

    @pytest.mark.asyncio
    async def test_list_tags_are_replaced_as_a_whole(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        item = await _tagged_item(db_session, test_user.id)

        response = await client.patch(
            f"/api/v1/items/{item.id}",
            json={"tags": {"season": ["all-season"], "style": ["elegant", "modern"]}},
            headers=auth_headers,
        )

        assert response.status_code == 200, response.json()
        data = response.json()
        assert data["season"] == ["all-season"]
        assert data["tags"]["season"] == ["all-season"]
        assert data["style"] == ["elegant", "modern"]
        assert data["tags"]["colors"] == AI_TAGS["colors"]

    @pytest.mark.asyncio
    async def test_editing_a_tag_marks_the_item_manually_tagged(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        item = await _tagged_item(db_session, test_user.id)

        response = await client.patch(
            f"/api/v1/items/{item.id}",
            json={"tags": {"pattern": "plaid"}},
            headers=auth_headers,
        )

        assert response.status_code == 200, response.json()
        assert response.json()["tagged_by"] == "manual"


async def _reanalyse(db_session: AsyncSession, monkeypatch, item: ClothingItem, ai: ClothingTags):
    item_id = item.id

    class _StubAI:
        def __init__(self, *args, **kwargs):
            pass

        async def analyze_image(self, path):
            return ai

    monkeypatch.setattr(tagging, "AIService", _StubAI)
    with (
        patch("app.workers.tagging.get_db_session", return_value=db_session),
        patch.object(db_session, "close", new_callable=AsyncMock),
    ):
        result = await tagging.tag_item_image({}, str(item_id), __file__)
    assert result["status"] == "success"

    db_session.expire_all()
    return (
        await db_session.execute(select(ClothingItem).where(ClothingItem.id == item_id))
    ).scalar_one()


FRESH_AI = ClothingTags(
    type="jacket",
    primary_color="black",
    colors=["black"],
    pattern="solid",
    material="linen",
    style=["modern"],
    season=["summer"],
    formality="formal",
    fit="oversized",
    confidence=0.9,
)


class TestReanalysisKeepsEdits:
    @pytest.mark.asyncio
    async def test_edited_tags_survive_in_column_and_view(
        self, db_session: AsyncSession, test_user, monkeypatch
    ):
        item = await _tagged_item(db_session, test_user.id)
        item.status = ItemStatus.processing
        await db_session.commit()

        refreshed = await _reanalyse(db_session, monkeypatch, item, FRESH_AI)

        # Columns keep set values (the rule predates tag editing) and the view now
        # agrees with them instead of showing the AI's discarded answer.
        assert refreshed.formality == AI_TAGS["formality"]
        assert refreshed.tags["formality"] == AI_TAGS["formality"]
        assert refreshed.tags["material"] == AI_TAGS["material"]
        assert refreshed.tags["style"] == AI_TAGS["style"]
        # fit has no column, so only the view can keep it.
        assert refreshed.tags["fit"] == AI_TAGS["fit"]

    @pytest.mark.asyncio
    async def test_cleared_tag_is_filled_again(
        self, db_session: AsyncSession, test_user, monkeypatch
    ):
        item = await _tagged_item(db_session, test_user.id)
        item.material = None
        item.tags = {**AI_TAGS, "material": None, "fit": None}
        item.status = ItemStatus.processing
        await db_session.commit()

        refreshed = await _reanalyse(db_session, monkeypatch, item, FRESH_AI)

        assert refreshed.material == "linen"
        assert refreshed.tags["material"] == "linen"
        assert refreshed.tags["fit"] == "oversized"

    @pytest.mark.asyncio
    async def test_first_analysis_shows_the_ai_result(
        self, db_session: AsyncSession, test_user, monkeypatch
    ):
        item = ClothingItem(
            user_id=test_user.id,
            type="unknown",
            image_path="test/fresh.jpg",
            status=ItemStatus.processing,
        )
        db_session.add(item)
        await db_session.commit()

        refreshed = await _reanalyse(db_session, monkeypatch, item, FRESH_AI)

        assert refreshed.formality == "formal"
        assert refreshed.tags["formality"] == "formal"
        assert refreshed.tags["colors"] == ["black"]
        assert refreshed.tags["fit"] == "oversized"


class TestTagOptions:
    @pytest.mark.asyncio
    async def test_offers_exactly_what_the_tagger_accepts(self, client: AsyncClient, auth_headers):
        from app.services import ai_service

        response = await client.get("/api/v1/items/tag-options", headers=auth_headers)

        assert response.status_code == 200, response.json()
        data = response.json()
        assert set(data["colors"]) == ai_service.VALID_COLORS
        assert set(data["patterns"]) == ai_service.VALID_PATTERNS
        assert set(data["materials"]) == ai_service.VALID_MATERIALS
        assert set(data["styles"]) == ai_service.VALID_STYLES
        assert set(data["fits"]) == ai_service.VALID_FIT
        # Ordered by meaning, not alphabetically, so the editor reads naturally.
        assert data["formality"] == [
            "very-casual",
            "casual",
            "smart-casual",
            "business-casual",
            "formal",
        ]
        assert data["seasons"] == ["spring", "summer", "fall", "winter", "all-season"]
