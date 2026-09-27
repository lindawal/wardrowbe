"""Step 2 of inspiration looks: matching against the wardrobe, swapping picks, and
restyling a look as a regular outfit."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inspiration import InspirationLook, InspirationLookItem, InspirationStatus
from app.models.item import ClothingItem, ItemStatus
from app.models.outfit import Outfit
from app.models.user import User
from app.services.ai_service import AIService, ClothingTags
from app.services.inspiration_matching_service import (
    MATCH_SUGGESTION_COUNT,
    RELATED_TYPE_FACTOR,
    UNKNOWN,
    assign_match,
    color_score,
    equal_score,
    fit_score,
    formality_score,
    item_fit,
    match_look_items,
    rank_candidates,
    score_candidate,
    style_score,
)
from app.workers.inspiration import analyze_inspiration_look

INSPIRATION_ENDPOINT = "/api/v1/inspiration"


# --- helpers -----------------------------------------------------------------


def _look_item(item_type: str = "t-shirt", position: int = 0, **kwargs) -> InspirationLookItem:
    return InspirationLookItem(type=item_type, position=position, **kwargs)


def _wardrobe_item(item_type: str = "t-shirt", **kwargs) -> ClothingItem:
    kwargs.setdefault("id", uuid4())
    return ClothingItem(
        user_id=uuid4(),
        type=item_type,
        image_path=f"test/{uuid4()}.jpg",
        status=ItemStatus.ready,
        **kwargs,
    )


async def _add_item(
    db_session: AsyncSession, user_id, item_type: str = "t-shirt", **kwargs
) -> ClothingItem:
    kwargs.setdefault("status", ItemStatus.ready)
    item = ClothingItem(
        user_id=user_id,
        type=item_type,
        image_path=f"test/{uuid4()}.jpg",
        thumbnail_path=f"test/{uuid4()}_thumb.jpg",
        **kwargs,
    )
    db_session.add(item)
    await db_session.commit()
    return item


async def _add_archived_item(
    db_session: AsyncSession, user_id, item_type: str = "t-shirt", **kwargs
) -> ClothingItem:
    return await _add_item(
        db_session,
        user_id,
        item_type,
        status=ItemStatus.archived,
        is_archived=True,
        archived_at=datetime.now(UTC),
        **kwargs,
    )


async def _make_look(
    db_session: AsyncSession,
    user_id,
    items: list[dict],
    *,
    status: InspirationStatus = InspirationStatus.analyzed,
    matched: bool = True,
) -> InspirationLook:
    look = InspirationLook(
        user_id=user_id,
        photo_path=f"test/{uuid4()}.jpg",
        status=status,
        matched_at=datetime.now(UTC) if matched else None,
    )
    db_session.add(look)
    await db_session.flush()
    for i, data in enumerate(items):
        db_session.add(InspirationLookItem(inspiration_look_id=look.id, position=i, **data))
    await db_session.commit()
    return look


async def _look_items(db_session: AsyncSession, look_id) -> list[InspirationLookItem]:
    result = await db_session.execute(
        select(InspirationLookItem)
        .where(InspirationLookItem.inspiration_look_id == look_id)
        .order_by(InspirationLookItem.position)
        .execution_options(populate_existing=True)
    )
    return list(result.scalars().all())


async def _other_user(db_session: AsyncSession) -> User:
    other_id = uuid4()
    other = User(
        id=other_id,
        external_id=f"test-user-{other_id}",
        email=f"test-{other_id}@example.com",
        display_name="Other User",
        timezone="UTC",
        is_active=True,
        onboarding_completed=False,
    )
    db_session.add(other)
    await db_session.commit()
    return other


# --- scoring (no database) ---------------------------------------------------


class TestScoring:
    def test_exact_type_outranks_related_type(self):
        look_item = _look_item("jeans", primary_color="blue")
        jeans = _wardrobe_item("jeans", primary_color="blue")
        pants = _wardrobe_item("pants", primary_color="blue")

        ranked = rank_candidates(look_item, [pants, jeans])

        assert [c.item.id for c in ranked] == [jeans.id, pants.id]
        assert ranked[1].score == pytest.approx(ranked[0].score * RELATED_TYPE_FACTOR, abs=1e-3)

    def test_unrelated_type_is_not_a_candidate(self):
        look_item = _look_item("jeans", primary_color="blue")
        skirt = _wardrobe_item("skirt", primary_color="blue")

        assert rank_candidates(look_item, [skirt]) == []
        assert score_candidate(look_item, skirt) == 0.0

    def test_unknown_type_gets_no_candidates(self):
        look_item = _look_item("unknown", primary_color="black")
        assert rank_candidates(look_item, [_wardrobe_item("t-shirt", primary_color="black")]) == []

    def test_same_type_is_a_candidate_even_if_nothing_else_fits(self):
        look_item = _look_item("t-shirt", primary_color="red", pattern="striped")
        tee = _wardrobe_item("t-shirt", primary_color="green", pattern="solid")

        ranked = rank_candidates(look_item, [tee])
        assert [c.item.id for c in ranked] == [tee.id]

    def test_color_score_levels(self):
        assert color_score("black", [], "black", []) == 1.0
        assert color_score("navy", [], "black", []) == 0.6
        assert color_score("black", [], "white", ["white", "black"]) == 0.4
        assert color_score("red", [], "green", ["green"]) == 0.0

    def test_missing_tags_score_neutral(self):
        assert color_score(None, [], "black", []) == UNKNOWN
        assert color_score("black", [], None, []) == UNKNOWN
        assert equal_score(None, "solid") == UNKNOWN
        assert style_score([], ["casual"]) == UNKNOWN
        assert formality_score("casual", None) == UNKNOWN
        assert fit_score(None, "slim") == UNKNOWN

    def test_graded_scores(self):
        assert style_score(["casual", "minimalist"], ["casual"]) == 0.5
        assert formality_score("casual", "smart-casual") == 0.5
        assert formality_score("casual", "formal") == 0.0
        assert fit_score("relaxed", "oversized") == 0.5
        assert fit_score("slim", "oversized") == 0.0

    def test_fit_is_read_from_the_items_json_tags(self):
        assert item_fit(_wardrobe_item(tags={"fit": "Oversized"})) == "oversized"
        assert item_fit(_wardrobe_item(tags={})) is None
        assert item_fit(_wardrobe_item()) is None

    def test_closer_attributes_rank_first(self):
        look_item = _look_item(
            "t-shirt",
            primary_color="black",
            pattern="solid",
            material="cotton",
            style=["casual"],
            formality="casual",
            fit="slim",
        )
        exact = _wardrobe_item(
            "t-shirt",
            primary_color="black",
            pattern="solid",
            material="cotton",
            style=["casual"],
            formality="casual",
            tags={"fit": "slim"},
        )
        striped = _wardrobe_item(
            "t-shirt", primary_color="black", pattern="striped", material="cotton"
        )
        white = _wardrobe_item("t-shirt", primary_color="white", pattern="solid")

        ranked = rank_candidates(look_item, [white, striped, exact])

        assert [c.item.id for c in ranked] == [exact.id, striped.id, white.id]
        assert ranked[0].score == pytest.approx(1.0)

    def test_ties_prefer_favorites(self):
        look_item = _look_item("t-shirt", primary_color="black")
        plain = _wardrobe_item("t-shirt", primary_color="black", favorite=False)
        favorite = _wardrobe_item("t-shirt", primary_color="black", favorite=True)

        ranked = rank_candidates(look_item, [plain, favorite])
        assert [c.item.id for c in ranked] == [favorite.id, plain.id]


class TestAssignment:
    def test_keeps_top_suggestions_and_preselects_the_best(self):
        look_item = _look_item("t-shirt", primary_color="black")
        best = _wardrobe_item("t-shirt", primary_color="black", pattern="solid")
        others = [_wardrobe_item("t-shirt", primary_color=c) for c in ("navy", "white", "red")]

        assign_match(look_item, [*others, best])

        assert len(look_item.suggested_item_ids) == MATCH_SUGGESTION_COUNT
        assert look_item.suggested_item_ids[0] == best.id
        assert look_item.matched_item_id == best.id

    def test_no_candidate_leaves_the_slot_empty(self):
        look_item = _look_item("boots", primary_color="black")

        assign_match(look_item, [_wardrobe_item("t-shirt")])

        assert look_item.suggested_item_ids == []
        assert look_item.matched_item_id is None

    def test_two_slots_do_not_get_the_same_item_preselected(self):
        tee_slot = _look_item("t-shirt", position=0, primary_color="black")
        blouse_slot = _look_item("blouse", position=1, primary_color="black")
        tee = _wardrobe_item("t-shirt", primary_color="black")
        blouse = _wardrobe_item("blouse", primary_color="black")

        match_look_items([blouse_slot, tee_slot], [tee, blouse])

        assert tee_slot.matched_item_id == tee.id
        assert blouse_slot.matched_item_id == blouse.id

    def test_slot_stays_empty_when_its_only_candidate_is_taken(self):
        tee_slot = _look_item("t-shirt", position=0, primary_color="black")
        blouse_slot = _look_item("blouse", position=1, primary_color="black")
        tee = _wardrobe_item("t-shirt", primary_color="black")

        match_look_items([tee_slot, blouse_slot], [tee])

        assert tee_slot.matched_item_id == tee.id
        assert blouse_slot.matched_item_id is None


# --- worker ------------------------------------------------------------------


class TestMatchingInAnalysisJob:
    @pytest.mark.asyncio
    async def test_matches_new_items_against_the_wardrobe(
        self, db_session: AsyncSession, test_user
    ):
        black_tee = await _add_item(db_session, test_user.id, "t-shirt", primary_color="black")
        white_tee = await _add_item(db_session, test_user.id, "t-shirt", primary_color="white")
        await _add_archived_item(db_session, test_user.id, "t-shirt", primary_color="black")
        look = InspirationLook(
            user_id=test_user.id, photo_path="test/look.jpg", status=InspirationStatus.pending
        )
        db_session.add(look)
        await db_session.commit()

        with (
            patch("app.workers.inspiration.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch.object(AIService, "analyze_outfit_look", new_callable=AsyncMock) as analyze,
        ):
            analyze.return_value = [
                ClothingTags(type="t-shirt", primary_color="black"),
                ClothingTags(type="sneakers", primary_color="white"),
            ]
            result = await analyze_inspiration_look({"job_try": 1}, str(look.id), __file__)

        assert result["status"] == "success"
        assert result["matched"] is True

        await db_session.refresh(look)
        assert look.status == InspirationStatus.analyzed
        assert look.matched_at is not None

        stored = await _look_items(db_session, look.id)
        assert stored[0].matched_item_id == black_tee.id
        # The archived black t-shirt is never suggested.
        assert stored[0].suggested_item_ids == [black_tee.id, white_tee.id]
        assert stored[1].matched_item_id is None
        assert stored[1].suggested_item_ids == []

    @pytest.mark.asyncio
    async def test_matching_failure_still_finishes_the_analysis(
        self, db_session: AsyncSession, test_user
    ):
        look = InspirationLook(
            user_id=test_user.id, photo_path="test/look.jpg", status=InspirationStatus.pending
        )
        db_session.add(look)
        await db_session.commit()

        with (
            patch("app.workers.inspiration.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch.object(AIService, "analyze_outfit_look", new_callable=AsyncMock) as analyze,
            patch("app.workers.inspiration.match_look", new_callable=AsyncMock) as match,
        ):
            analyze.return_value = [ClothingTags(type="t-shirt", primary_color="black")]
            match.side_effect = RuntimeError("database hiccup")
            result = await analyze_inspiration_look({"job_try": 1}, str(look.id), __file__)

        assert result["status"] == "success"
        assert result["matched"] is False

        await db_session.refresh(look)
        assert look.status == InspirationStatus.analyzed
        assert look.matched_at is None
        assert len(await _look_items(db_session, look.id)) == 1


# --- API ---------------------------------------------------------------------


class TestLookDetailWithMatches:
    @pytest.mark.asyncio
    async def test_resolves_pick_and_suggestions(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        first = await _add_item(db_session, test_user.id, "t-shirt", name="Black tee")
        second = await _add_item(db_session, test_user.id, "t-shirt")
        archived = await _add_archived_item(db_session, test_user.id, "t-shirt")
        look = await _make_look(
            db_session,
            test_user.id,
            [
                {
                    "type": "t-shirt",
                    "matched_item_id": first.id,
                    "suggested_item_ids": [first.id, archived.id, second.id],
                }
            ],
        )

        response = await client.get(f"{INSPIRATION_ENDPOINT}/{look.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["matched_at"] is not None
        item = data["items"][0]
        assert item["matched_item"]["id"] == str(first.id)
        assert item["matched_item"]["name"] == "Black tee"
        assert item["matched_item"]["thumbnail_url"]
        # Rank order kept, archived item dropped.
        assert [s["id"] for s in item["suggested_items"]] == [str(first.id), str(second.id)]

    @pytest.mark.asyncio
    async def test_pick_that_was_archived_since_is_not_resolved(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        archived = await _add_archived_item(db_session, test_user.id, "t-shirt")
        look = await _make_look(
            db_session,
            test_user.id,
            [{"type": "t-shirt", "matched_item_id": archived.id, "suggested_item_ids": []}],
        )

        response = await client.get(f"{INSPIRATION_ENDPOINT}/{look.id}", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["items"][0]["matched_item"] is None


class TestSetMatch:
    @pytest.mark.asyncio
    async def test_picks_any_usable_item(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        suggested = await _add_item(db_session, test_user.id, "t-shirt")
        other = await _add_item(db_session, test_user.id, "sweater")
        look = await _make_look(
            db_session,
            test_user.id,
            [
                {
                    "type": "t-shirt",
                    "matched_item_id": suggested.id,
                    "suggested_item_ids": [suggested.id],
                }
            ],
        )
        item_id = (await _look_items(db_session, look.id))[0].id

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{item_id}/match",
            json={"wardrobe_item_id": str(other.id)},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["matched_item_id"] == str(other.id)
        assert data["matched_item"]["id"] == str(other.id)
        # Suggestions stay as matched; only the pick changes.
        assert [s["id"] for s in data["suggested_items"]] == [str(suggested.id)]

    @pytest.mark.asyncio
    async def test_null_clears_the_slot(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        tee = await _add_item(db_session, test_user.id, "t-shirt")
        look = await _make_look(
            db_session,
            test_user.id,
            [{"type": "t-shirt", "matched_item_id": tee.id, "suggested_item_ids": [tee.id]}],
        )
        item_id = (await _look_items(db_session, look.id))[0].id

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{item_id}/match",
            json={"wardrobe_item_id": None},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["matched_item_id"] is None
        assert response.json()["matched_item"] is None

    @pytest.mark.asyncio
    async def test_rejects_someone_elses_item(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        other = await _other_user(db_session)
        foreign = await _add_item(db_session, other.id, "t-shirt")
        look = await _make_look(db_session, test_user.id, [{"type": "t-shirt"}])
        item_id = (await _look_items(db_session, look.id))[0].id

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{item_id}/match",
            json={"wardrobe_item_id": str(foreign.id)},
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "WARDROBE_ITEM_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_rejects_archived_item(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        archived = await _add_archived_item(db_session, test_user.id, "t-shirt")
        look = await _make_look(db_session, test_user.id, [{"type": "t-shirt"}])
        item_id = (await _look_items(db_session, look.id))[0].id

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{item_id}/match",
            json={"wardrobe_item_id": str(archived.id)},
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_404_for_missing_look_item(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look(db_session, test_user.id, [{"type": "t-shirt"}])

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{uuid4()}/match",
            json={"wardrobe_item_id": None},
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "INSPIRATION_ITEM_NOT_FOUND"


class TestTagCorrectionRematches:
    @pytest.mark.asyncio
    async def test_changing_the_type_rematches_the_item(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        jeans = await _add_item(db_session, test_user.id, "jeans", primary_color="blue")
        sneakers = await _add_item(db_session, test_user.id, "sneakers", primary_color="white")
        look = await _make_look(
            db_session,
            test_user.id,
            [
                {
                    "type": "jeans",
                    "primary_color": "white",
                    "matched_item_id": jeans.id,
                    "suggested_item_ids": [jeans.id],
                }
            ],
        )
        item_id = (await _look_items(db_session, look.id))[0].id

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{item_id}",
            json={"type": "sneakers"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "sneakers"
        assert data["matched_item"]["id"] == str(sneakers.id)
        assert [s["id"] for s in data["suggested_items"]] == [str(sneakers.id)]

    @pytest.mark.asyncio
    async def test_description_only_keeps_the_manual_pick(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        best = await _add_item(db_session, test_user.id, "t-shirt", primary_color="black")
        picked = await _add_item(db_session, test_user.id, "t-shirt", primary_color="white")
        look = await _make_look(
            db_session,
            test_user.id,
            [
                {
                    "type": "t-shirt",
                    "primary_color": "black",
                    "matched_item_id": picked.id,
                    "suggested_item_ids": [best.id, picked.id],
                }
            ],
        )
        item_id = (await _look_items(db_session, look.id))[0].id

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{item_id}",
            json={"description": "boxy black tee"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["matched_item"]["id"] == str(picked.id)

    @pytest.mark.asyncio
    async def test_never_matched_look_is_not_matched_by_a_correction(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        await _add_item(db_session, test_user.id, "sneakers")
        look = await _make_look(db_session, test_user.id, [{"type": "jeans"}], matched=False)
        item_id = (await _look_items(db_session, look.id))[0].id

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{item_id}",
            json={"type": "sneakers"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["matched_item"] is None
        assert response.json()["suggested_items"] == []


class TestRematchLook:
    @pytest.mark.asyncio
    async def test_rematch_resets_picks_and_sets_matched_at(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        best = await _add_item(db_session, test_user.id, "t-shirt", primary_color="black")
        picked = await _add_item(db_session, test_user.id, "t-shirt", primary_color="red")
        look = await _make_look(
            db_session,
            test_user.id,
            [
                {
                    "type": "t-shirt",
                    "primary_color": "black",
                    "matched_item_id": picked.id,
                    "suggested_item_ids": [],
                }
            ],
            matched=False,
        )

        response = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/match", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["matched_at"] is not None
        assert data["items"][0]["matched_item"]["id"] == str(best.id)
        assert [s["id"] for s in data["items"][0]["suggested_items"]] == [
            str(best.id),
            str(picked.id),
        ]

    @pytest.mark.asyncio
    async def test_409_while_not_analyzed(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look(
            db_session, test_user.id, [], status=InspirationStatus.analyzing, matched=False
        )

        response = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/match", headers=auth_headers
        )

        assert response.status_code == 409
        assert response.json()["detail"]["error_code"] == "INSPIRATION_LOOK_NOT_ANALYZED"


class TestRecreateOutfit:
    @pytest.mark.asyncio
    async def test_creates_pending_outfit_from_the_picks(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        tee = await _add_item(db_session, test_user.id, "t-shirt")
        jeans = await _add_item(db_session, test_user.id, "jeans")
        look = await _make_look(
            db_session,
            test_user.id,
            [
                {"type": "t-shirt", "matched_item_id": tee.id},
                {"type": "sneakers"},  # left empty -> skipped
                {"type": "jeans", "matched_item_id": jeans.id},
                {"type": "blouse", "matched_item_id": tee.id},  # same pick -> used once
            ],
        )

        response = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/recreate",
            json={"occasion": "Casual", "name": "  Street look  "},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["inspiration_look_id"] == str(look.id)
        assert data["occasion"] == "casual"
        assert data["name"] == "Street look"
        assert data["source"] == "external"
        assert data["status"] == "pending"
        assert [i["id"] for i in data["items"]] == [str(tee.id), str(jeans.id)]

    @pytest.mark.asyncio
    async def test_skips_picks_that_are_no_longer_usable(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        tee = await _add_item(db_session, test_user.id, "t-shirt")
        archived = await _add_archived_item(db_session, test_user.id, "jeans")
        look = await _make_look(
            db_session,
            test_user.id,
            [
                {"type": "t-shirt", "matched_item_id": tee.id},
                {"type": "jeans", "matched_item_id": archived.id},
            ],
        )

        response = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/recreate",
            json={"occasion": "work"},
            headers=auth_headers,
        )

        assert response.status_code == 201
        assert [i["id"] for i in response.json()["items"]] == [str(tee.id)]

    @pytest.mark.asyncio
    async def test_400_when_nothing_is_picked(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look(db_session, test_user.id, [{"type": "t-shirt"}])

        response = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/recreate",
            json={"occasion": "casual"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "NO_ITEMS_SELECTED"

    @pytest.mark.asyncio
    async def test_rejects_unknown_occasion(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        tee = await _add_item(db_session, test_user.id, "t-shirt")
        look = await _make_look(
            db_session, test_user.id, [{"type": "t-shirt", "matched_item_id": tee.id}]
        )

        response = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/recreate",
            json={"occasion": "gala"},
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_409_while_not_analyzed(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look(
            db_session, test_user.id, [], status=InspirationStatus.pending, matched=False
        )

        response = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/recreate",
            json={"occasion": "casual"},
            headers=auth_headers,
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_404_for_someone_elses_look(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        other = await _other_user(db_session)
        tee = await _add_item(db_session, other.id, "t-shirt")
        look = await _make_look(
            db_session, other.id, [{"type": "t-shirt", "matched_item_id": tee.id}]
        )

        response = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/recreate",
            json={"occasion": "casual"},
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_deleting_the_look_keeps_the_outfit(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        tee = await _add_item(db_session, test_user.id, "t-shirt")
        look = await _make_look(
            db_session, test_user.id, [{"type": "t-shirt", "matched_item_id": tee.id}]
        )
        created = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/recreate",
            json={"occasion": "casual"},
            headers=auth_headers,
        )
        outfit_id = created.json()["id"]

        with patch("app.services.inspiration_service.delete_photo_files"):
            deleted = await client.delete(f"{INSPIRATION_ENDPOINT}/{look.id}", headers=auth_headers)
        assert deleted.status_code == 204

        db_session.expire_all()
        outfit = (
            await db_session.execute(select(Outfit).where(Outfit.id == UUID(outfit_id)))
        ).scalar_one()
        assert outfit.inspiration_look_id is None


# --- adding and removing pieces by hand ----------------------------------------


class TestAddItem:
    @pytest.mark.asyncio
    async def test_adds_piece_last_and_matches_it(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        sneakers = await _add_item(db_session, test_user.id, "sneakers", primary_color="white")
        look = await _make_look(db_session, test_user.id, [{"type": "t-shirt"}])

        response = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items",
            json={"type": "Sneakers", "primary_color": "white", "description": "white sneakers"},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "sneakers"
        assert data["position"] == 1
        assert data["description"] == "white sneakers"
        assert data["matched_item"]["id"] == str(sneakers.id)

        detail = await client.get(f"{INSPIRATION_ENDPOINT}/{look.id}", headers=auth_headers)
        assert [i["type"] for i in detail.json()["items"]] == ["t-shirt", "sneakers"]

    @pytest.mark.asyncio
    async def test_never_matched_look_stays_unmatched(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        await _add_item(db_session, test_user.id, "sneakers")
        look = await _make_look(db_session, test_user.id, [], matched=False)

        response = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items",
            json={"type": "sneakers"},
            headers=auth_headers,
        )

        assert response.status_code == 201
        assert response.json()["position"] == 0
        assert response.json()["matched_item"] is None
        assert response.json()["suggested_items"] == []

    @pytest.mark.asyncio
    async def test_type_is_required_and_validated(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look(db_session, test_user.id, [])

        missing = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items",
            json={"primary_color": "black"},
            headers=auth_headers,
        )
        invalid = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items",
            json={"type": "cape"},
            headers=auth_headers,
        )

        assert missing.status_code == 422
        assert invalid.status_code == 422

    @pytest.mark.asyncio
    async def test_409_while_analyzing(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look(
            db_session, test_user.id, [], status=InspirationStatus.analyzing, matched=False
        )

        response = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items",
            json={"type": "t-shirt"},
            headers=auth_headers,
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_404_for_someone_elses_look(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        other = await _other_user(db_session)
        look = await _make_look(db_session, other.id, [])

        response = await client.post(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items",
            json={"type": "t-shirt"},
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestDeleteItem:
    @pytest.mark.asyncio
    async def test_removes_the_piece(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look(db_session, test_user.id, [{"type": "t-shirt"}, {"type": "hat"}])
        hat_id = (await _look_items(db_session, look.id))[1].id

        response = await client.delete(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{hat_id}", headers=auth_headers
        )

        assert response.status_code == 204
        assert [i.type for i in await _look_items(db_session, look.id)] == ["t-shirt"]

    @pytest.mark.asyncio
    async def test_404_for_missing_item(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look(db_session, test_user.id, [{"type": "t-shirt"}])

        response = await client.delete(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{uuid4()}", headers=auth_headers
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_404_for_someone_elses_look(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        other = await _other_user(db_session)
        look = await _make_look(db_session, other.id, [{"type": "t-shirt"}])
        item_id = (await _look_items(db_session, look.id))[0].id

        response = await client.delete(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{item_id}", headers=auth_headers
        )

        assert response.status_code == 404
        assert len(await _look_items(db_session, look.id)) == 1
