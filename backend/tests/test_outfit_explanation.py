import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.item import ClothingItem, ItemStatus
from app.models.outfit import OutfitSource
from app.models.user import User
from app.services.ai_service import AIService, TextGenerationResult
from app.services.outfit_explanation import (
    describe_item,
    explain_outfit,
    parse_explanation,
    strip_explanation,
)
from app.services.pairing_service import PairingService
from app.services.recommendation_service import RecommendationService
from app.services.weather_service import WeatherData

GROUNDED = {
    "headline": "Soft grey layers",
    "highlights": ["The grey wool sweater softens the dark denim."],
    "styling_tip": "Push the sweater sleeves to the elbow.",
}

# What the selection call used to return alongside the numbers: prose about a
# garment that was never selected. It must never reach the stored outfit.
UNGROUNDED = {
    "headline": "Navy bomber night",
    "highlights": ["The navy bomber jacket adds a sporty edge."],
    "styling_tip": "Pair the bomber with black loafers.",
}


def _item(user_id, item_type, **kwargs) -> ClothingItem:
    return ClothingItem(
        user_id=user_id,
        type=item_type,
        image_path=f"test/{uuid4()}.jpg",
        status=ItemStatus.ready,
        **kwargs,
    )


def _weather() -> WeatherData:
    return WeatherData(
        temperature=14,
        feels_like=12,
        humidity=60,
        precipitation_chance=10,
        precipitation_mm=0,
        wind_speed=5,
        condition="cloudy",
        condition_code=3,
        is_day=True,
        uv_index=1,
        timestamp=datetime.utcnow(),
    )


def _ai_service(response: str | Exception) -> MagicMock:
    service = MagicMock()
    if isinstance(response, Exception):
        service.generate_text = AsyncMock(side_effect=response)
    else:
        service.generate_text = AsyncMock(return_value=response)
    return service


def _outfit_section(prompt: str) -> str:
    """Only the item list: the template's own example text names garments too."""
    return prompt.split("THE OUTFIT", 1)[1].split("RULES:", 1)[0]


class TestParseExplanation:
    def test_plain_json(self):
        assert parse_explanation(json.dumps(GROUNDED)) == GROUNDED

    def test_fenced_json(self):
        assert parse_explanation(f"```json\n{json.dumps(GROUNDED)}\n```") == GROUNDED

    def test_json_wrapped_in_prose(self):
        content = f"Here is the explanation:\n{json.dumps(GROUNDED)}\nHope that helps!"
        assert parse_explanation(content) == GROUNDED

    def test_unparseable_returns_none(self):
        assert parse_explanation("The outfit looks great.") is None

    def test_wrong_types_are_dropped_not_crashed_on(self):
        content = json.dumps({"headline": 42, "highlights": ["  ok  ", "", 7], "styling_tip": "  "})
        assert parse_explanation(content) == {
            "headline": None,
            "highlights": ["ok"],
            "styling_tip": None,
        }

    def test_nothing_usable_returns_none(self):
        assert parse_explanation(json.dumps({"headline": "", "highlights": []})) is None


class TestStripExplanation:
    def test_removes_prose_keeps_selection_and_bookkeeping(self):
        data = {
            "items": [1, 2],
            "_ai_model": "qwen2.5:3b",
            **UNGROUNDED,
            "reasoning": "legacy prose",
            "style_notes": "legacy tip",
        }
        strip_explanation(data)
        assert data == {"items": [1, 2], "_ai_model": "qwen2.5:3b"}


class TestDescribeItem:
    def test_includes_name_and_attributes(self):
        item = _item(
            uuid4(),
            "sweater",
            subtype="crewneck",
            primary_color="gray",
            material="wool",
            name="Winter favourite",
        )
        assert describe_item(item) == '"Winter favourite" | crewneck (sweater) | gray | wool'


class TestExplainOutfit:
    @pytest.mark.asyncio
    async def test_prompt_lists_only_the_given_items(self):
        user_id = uuid4()
        sweater = _item(user_id, "sweater", primary_color="gray")
        jeans = _item(user_id, "jeans", primary_color="blue")
        service = _ai_service(json.dumps(GROUNDED))

        result = await explain_outfit(
            service, [sweater, jeans], occasion="casual", weather=_weather()
        )

        assert result == GROUNDED
        section = _outfit_section(service.generate_text.call_args.args[0])
        assert "sweater | gray" in section
        assert "jeans | blue" in section
        assert "bomber" not in section

    @pytest.mark.asyncio
    async def test_model_failure_returns_none_instead_of_raising(self):
        sweater = _item(uuid4(), "sweater")
        service = _ai_service(RuntimeError("endpoint down"))

        assert await explain_outfit(service, [sweater], occasion="casual") is None

    @pytest.mark.asyncio
    async def test_no_items_skips_the_model_call(self):
        service = _ai_service(json.dumps(GROUNDED))

        assert await explain_outfit(service, [], occasion="casual") is None
        service.generate_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_focus_item_replaces_occasion_context(self):
        user_id = uuid4()
        shirt = _item(user_id, "shirt", primary_color="white")
        service = _ai_service(json.dumps(GROUNDED))

        await explain_outfit(service, [shirt], focus_item=shirt)

        prompt = service.generate_text.call_args.args[0]
        assert "Built around: shirt | white" in prompt
        assert "Occasion:" not in prompt


class TestRecommendationGrounding:
    @pytest.mark.asyncio
    async def test_stored_text_comes_from_kept_items_not_selection(self, db_session, test_user):
        sweater = _item(test_user.id, "sweater", primary_color="gray", material="wool")
        jeans = _item(test_user.id, "jeans", primary_color="blue")
        db_session.add_all([sweater, jeans])
        await db_session.commit()

        service = RecommendationService(db_session)
        ai_service = _ai_service(json.dumps(GROUNDED))

        outfit = await service._materialize_outfit(
            {"items": [1, 2], **UNGROUNDED},
            test_user,
            _weather(),
            occasion="casual",
            source=OutfitSource.on_demand,
            number_map={1: sweater.id, 2: jeans.id},
            ai_service=ai_service,
            time_of_day="evening",
        )

        assert outfit.reasoning == GROUNDED["headline"]
        assert outfit.style_notes == GROUNDED["styling_tip"]
        assert outfit.ai_raw_response["highlights"] == GROUNDED["highlights"]
        assert "bomber" not in json.dumps(outfit.ai_raw_response)

    @pytest.mark.asyncio
    async def test_items_removed_by_dedup_are_not_explained(self, db_session, test_user):
        dress = _item(test_user.id, "dress", primary_color="black")
        pants = _item(test_user.id, "pants", primary_color="navy")
        shoes = _item(test_user.id, "shoes", primary_color="black")
        db_session.add_all([dress, pants, shoes])
        await db_session.commit()

        service = RecommendationService(db_session)
        ai_service = _ai_service(json.dumps(GROUNDED))

        outfit = await service._materialize_outfit(
            {"items": [1, 2, 3]},
            test_user,
            _weather(),
            occasion="casual",
            source=OutfitSource.on_demand,
            number_map={1: dress.id, 2: pants.id, 3: shoes.id},
            ai_service=ai_service,
        )

        assert pants.id not in {oi.item_id for oi in outfit.items}
        section = _outfit_section(ai_service.generate_text.call_args.args[0])
        assert "dress" in section
        assert "pants" not in section

    @pytest.mark.asyncio
    async def test_failed_explanation_keeps_outfit_and_drops_ungrounded_text(
        self, db_session, test_user
    ):
        sweater = _item(test_user.id, "sweater")
        jeans = _item(test_user.id, "jeans")
        db_session.add_all([sweater, jeans])
        await db_session.commit()

        service = RecommendationService(db_session)

        outfit = await service._materialize_outfit(
            {"items": [1, 2], **UNGROUNDED},
            test_user,
            _weather(),
            occasion="casual",
            source=OutfitSource.on_demand,
            number_map={1: sweater.id, 2: jeans.id},
            ai_service=_ai_service("not json at all"),
        )

        assert {oi.item_id for oi in outfit.items} == {sweater.id, jeans.id}
        assert outfit.reasoning is None
        assert outfit.style_notes is None
        assert "highlights" not in outfit.ai_raw_response


class TestPairingGrounding:
    @pytest.mark.asyncio
    async def test_pairing_text_comes_from_kept_items(self, db_session, test_user):
        shirt = _item(test_user.id, "shirt", primary_color="white")
        jeans = _item(test_user.id, "jeans", primary_color="blue")
        sneakers = _item(test_user.id, "sneakers", primary_color="white")
        db_session.add_all([shirt, jeans, sneakers])
        await db_session.commit()

        # generate_pairings reads user.preferences, which is not loaded by the fixture.
        user = (
            await db_session.execute(
                select(User).where(User.id == test_user.id).options(selectinload(User.preferences))
            )
        ).scalar_one()

        selection = TextGenerationResult(
            content=json.dumps([{"items": [1, 2, 3], **UNGROUNDED}]),
            model="qwen2.5:3b",
            endpoint="default",
        )
        generate_text = AsyncMock(side_effect=[selection, json.dumps(GROUNDED)])

        with patch.object(AIService, "generate_text", generate_text):
            result = await PairingService(db_session).generate_pairings(
                user, shirt.id, num_pairings=1
            )

        assert len(result.outfits) == 1
        assert result.discarded == 0
        outfit = result.outfits[0]
        assert outfit.reasoning == GROUNDED["headline"]
        assert outfit.ai_raw_response["highlights"] == GROUNDED["highlights"]
        assert "bomber" not in json.dumps(outfit.ai_raw_response)

        explanation_prompt = generate_text.call_args_list[1].args[0]
        assert "Built around: shirt | white" in explanation_prompt


class TestRecommendationRegionFill:
    @pytest.mark.asyncio
    async def test_missing_top_is_filled_with_best_ranked_top(self, db_session, test_user):
        # The reported case: the model picked only jeans and sneakers.
        jeans = _item(test_user.id, "jeans", primary_color="blue")
        sneakers = _item(test_user.id, "sneakers", primary_color="white")
        best_top = _item(test_user.id, "t-shirt", primary_color="white")
        worse_top = _item(test_user.id, "shirt", primary_color="orange")
        db_session.add_all([jeans, sneakers, best_top, worse_top])
        await db_session.commit()

        service = RecommendationService(db_session)
        ai_service = _ai_service(json.dumps(GROUNDED))

        outfit = await service._materialize_outfit(
            {"items": [1, 2]},
            test_user,
            _weather(),
            occasion="casual",
            source=OutfitSource.on_demand,
            # Numbered in ranking order, as _format_items_for_prompt produces it.
            number_map={1: jeans.id, 2: sneakers.id, 3: best_top.id, 4: worse_top.id},
            ai_service=ai_service,
        )

        item_ids = {oi.item_id for oi in outfit.items}
        assert item_ids == {jeans.id, sneakers.id, best_top.id}
        # Filled before the explanation, so the text covers the added top.
        section = _outfit_section(ai_service.generate_text.call_args.args[0])
        assert "t-shirt | white" in section

    @pytest.mark.asyncio
    async def test_complete_outfit_is_left_alone(self, db_session, test_user):
        # A distinct upper-body type from the spare t-shirt below, so the fill
        # logic has something other than "t-shirt" to recognize as covering
        # the upper region.
        shirt = _item(test_user.id, "blouse")
        jeans = _item(test_user.id, "jeans")
        sneakers = _item(test_user.id, "sneakers")
        spare = _item(test_user.id, "t-shirt")
        db_session.add_all([shirt, jeans, sneakers, spare])
        await db_session.commit()

        outfit = await RecommendationService(db_session)._materialize_outfit(
            {"items": [1, 2, 3]},
            test_user,
            _weather(),
            occasion="casual",
            source=OutfitSource.on_demand,
            number_map={1: shirt.id, 2: jeans.id, 3: sneakers.id, 4: spare.id},
        )

        assert {oi.item_id for oi in outfit.items} == {shirt.id, jeans.id, sneakers.id}

    @pytest.mark.asyncio
    async def test_no_candidate_for_region_keeps_outfit(self, db_session, test_user):
        jeans = _item(test_user.id, "jeans")
        sneakers = _item(test_user.id, "sneakers")
        db_session.add_all([jeans, sneakers])
        await db_session.commit()

        outfit = await RecommendationService(db_session)._materialize_outfit(
            {"items": [1, 2]},
            test_user,
            _weather(),
            occasion="casual",
            source=OutfitSource.on_demand,
            number_map={1: jeans.id, 2: sneakers.id},
        )

        assert {oi.item_id for oi in outfit.items} == {jeans.id, sneakers.id}


async def _user_with_preferences(db_session, test_user) -> User:
    # generate_pairings reads user.preferences, which the fixture does not load.
    return (
        await db_session.execute(
            select(User).where(User.id == test_user.id).options(selectinload(User.preferences))
        )
    ).scalar_one()


def _selection(pairings: list[list[int]]) -> TextGenerationResult:
    return TextGenerationResult(
        content=json.dumps([{"items": items} for items in pairings]),
        model="qwen2.5:3b",
        endpoint="default",
    )


class TestPairingDiscard:
    @pytest.mark.asyncio
    async def test_incomplete_pairing_is_discarded_and_counted(self, db_session, test_user):
        shirt = _item(test_user.id, "shirt")
        jeans = _item(test_user.id, "jeans")
        sneakers = _item(test_user.id, "sneakers")
        db_session.add_all([shirt, jeans, sneakers])
        await db_session.commit()
        user = await _user_with_preferences(db_session, test_user)

        # 2 and 3 are jeans and sneakers in database order. Whichever 2 is, the
        # shirt plus that one piece leaves a region the wardrobe could cover.
        generate_text = AsyncMock(
            side_effect=[_selection([[1, 2], [1, 2, 3]]), json.dumps(GROUNDED)]
        )

        with patch.object(AIService, "generate_text", generate_text):
            result = await PairingService(db_session).generate_pairings(
                user, shirt.id, num_pairings=2
            )

        assert len(result.outfits) == 1
        assert result.discarded == 1
        # Only the kept pairing was sent for an explanation.
        assert generate_text.call_count == 2

    @pytest.mark.asyncio
    async def test_region_the_wardrobe_cannot_cover_is_not_required(self, db_session, test_user):
        shirt = _item(test_user.id, "shirt")
        jeans = _item(test_user.id, "jeans")
        cap = _item(test_user.id, "hat")
        db_session.add_all([shirt, jeans, cap])
        await db_session.commit()
        user = await _user_with_preferences(db_session, test_user)

        # No shoes anywhere: requiring feet would discard every pairing.
        generate_text = AsyncMock(side_effect=[_selection([[1, 2, 3]]), json.dumps(GROUNDED)])

        with patch.object(AIService, "generate_text", generate_text):
            result = await PairingService(db_session).generate_pairings(
                user, shirt.id, num_pairings=1
            )

        assert len(result.outfits) == 1
        assert result.discarded == 0

    @pytest.mark.asyncio
    async def test_api_reports_discarded_count(self, client, auth_headers, db_session, test_user):
        shirt = _item(test_user.id, "shirt")
        jeans = _item(test_user.id, "jeans")
        sneakers = _item(test_user.id, "sneakers")
        db_session.add_all([shirt, jeans, sneakers])
        await db_session.commit()

        generate_text = AsyncMock(
            side_effect=[_selection([[1, 2], [1, 2, 3]]), json.dumps(GROUNDED)]
        )

        with patch.object(AIService, "generate_text", generate_text):
            response = await client.post(
                f"/api/v1/pairings/generate/{shirt.id}",
                json={"num_pairings": 2},
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["generated"] == 1
        assert body["discarded"] == 1
