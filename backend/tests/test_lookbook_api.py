from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import ClothingItem, ItemStatus
from app.models.outfit import Outfit, OutfitItem, OutfitSource, OutfitStatus
from app.models.user import User


def _make_item(user_id, item_type="shirt", season=None) -> ClothingItem:
    return ClothingItem(
        user_id=user_id,
        type=item_type,
        image_path=f"test/{uuid4()}.jpg",
        status=ItemStatus.ready,
        season=season or [],
    )


def _make_outfit(
    user_id,
    *,
    is_lookbook: bool = True,
    name: str | None = None,
    tags: list[str] | None = None,
    seasons: list[str] | None = None,
    weather_tags: list[str] | None = None,
    items: list[ClothingItem] | None = None,
) -> Outfit:
    outfit = Outfit(
        user_id=user_id,
        occasion="casual",
        scheduled_for=None if is_lookbook else date.today(),
        status=OutfitStatus.pending,
        source=OutfitSource.manual,
        name=name,
        tags=tags or [],
        seasons=seasons or [],
        weather_tags=weather_tags or [],
    )
    for i, item in enumerate(items or []):
        outfit.items.append(OutfitItem(item_id=item.id, position=i))
    return outfit


def _make_user() -> User:
    uid = uuid4()
    return User(
        id=uid,
        external_id=f"lookbook-other-{uid}",
        email=f"lookbook-other-{uid}@example.com",
        display_name="Other User",
        timezone="UTC",
        is_active=True,
    )


async def _persist(db_session: AsyncSession, *objects) -> None:
    db_session.add_all(objects)
    await db_session.commit()
    for obj in objects:
        await db_session.refresh(obj)


def _ids(response) -> set[str]:
    return {o["id"] for o in response.json()["outfits"]}


class TestLookbookListFilters:
    @pytest.mark.asyncio
    async def test_tags_match_any_value(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        work = _make_outfit(test_user.id, tags=["work"])
        gym = _make_outfit(test_user.id, tags=["gym"])
        untagged = _make_outfit(test_user.id)
        await _persist(db_session, work, gym, untagged)

        response = await client.get(
            "/api/v1/outfits?is_lookbook=true&tags=work", headers=auth_headers
        )
        assert response.status_code == 200
        assert _ids(response) == {str(work.id)}

        response = await client.get(
            "/api/v1/outfits?is_lookbook=true&tags=Work,GYM", headers=auth_headers
        )
        assert _ids(response) == {str(work.id), str(gym.id)}

    @pytest.mark.asyncio
    async def test_season_and_weather_filters_combine(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        cold_winter = _make_outfit(test_user.id, seasons=["winter"], weather_tags=["cold"])
        mild_winter = _make_outfit(test_user.id, seasons=["winter"], weather_tags=["mild"])
        summer = _make_outfit(test_user.id, seasons=["summer"], weather_tags=["warm"])
        await _persist(db_session, cold_winter, mild_winter, summer)

        response = await client.get(
            "/api/v1/outfits?is_lookbook=true&seasons=winter&weather_tags=cold",
            headers=auth_headers,
        )
        assert _ids(response) == {str(cold_winter.id)}

    @pytest.mark.asyncio
    async def test_invalid_filter_values_are_ignored(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        outfits = [_make_outfit(test_user.id, seasons=["summer"]), _make_outfit(test_user.id)]
        await _persist(db_session, *outfits)

        response = await client.get(
            "/api/v1/outfits?is_lookbook=true&seasons=monsoon&weather_tags=foggy",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 2

    @pytest.mark.asyncio
    async def test_tags_combine_with_search_and_stay_per_user(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        other_user = _make_user()
        await _persist(db_session, other_user)

        office = _make_outfit(test_user.id, name="Office blues", tags=["work"])
        meeting = _make_outfit(test_user.id, name="Board meeting", tags=["work"])
        foreign = _make_outfit(other_user.id, name="Office blues", tags=["work"])
        await _persist(db_session, office, meeting, foreign)

        response = await client.get(
            "/api/v1/outfits?is_lookbook=true&tags=work&search=office", headers=auth_headers
        )
        assert _ids(response) == {str(office.id)}


class TestLookbookTagCounts:
    @pytest.mark.asyncio
    async def test_counts_only_own_lookbook_outfits(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        other_user = _make_user()
        await _persist(db_session, other_user)

        await _persist(
            db_session,
            _make_outfit(test_user.id, tags=["work", "date"]),
            _make_outfit(test_user.id, tags=["work"]),
            _make_outfit(test_user.id),
            _make_outfit(test_user.id, is_lookbook=False, tags=["work", "gym"]),
            _make_outfit(other_user.id, tags=["work", "gym"]),
        )

        response = await client.get("/api/v1/outfits/lookbook/tags", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == {
            "total": 3,
            "tags": [{"tag": "work", "count": 2}, {"tag": "date", "count": 1}],
        }

    @pytest.mark.asyncio
    async def test_empty_lookbook(self, client: AsyncClient, auth_headers):
        response = await client.get("/api/v1/outfits/lookbook/tags", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"total": 0, "tags": []}


class TestPatchLookbookAttributes:
    @pytest.mark.asyncio
    async def test_normalizes_and_clears_independently(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        outfit = _make_outfit(test_user.id)
        await _persist(db_session, outfit)

        response = await client.patch(
            f"/api/v1/outfits/{outfit.id}",
            json={
                "tags": [" Work ", "work", "Date  Night"],
                "seasons": ["autumn"],
                "weather_tags": ["Rain"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == ["work", "date night"]
        assert data["seasons"] == ["fall"]
        assert data["weather_tags"] == ["rain"]

        response = await client.patch(
            f"/api/v1/outfits/{outfit.id}", json={"tags": []}, headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["tags"] == []
        assert response.json()["seasons"] == ["fall"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "payload",
        [
            {"tags": [f"tag{i}" for i in range(11)]},
            {"tags": ["work,gym"]},
            {"tags": ["x" * 31]},
            {"seasons": ["monsoon"]},
            {"weather_tags": ["foggy"]},
        ],
    )
    async def test_rejects_invalid_values(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession, payload
    ):
        outfit = _make_outfit(test_user.id)
        await _persist(db_session, outfit)

        response = await client.patch(
            f"/api/v1/outfits/{outfit.id}", json=payload, headers=auth_headers
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_patch_is_still_rejected(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        outfit = _make_outfit(test_user.id)
        await _persist(db_session, outfit)

        response = await client.patch(f"/api/v1/outfits/{outfit.id}", json={}, headers=auth_headers)
        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "PATCH_EMPTY"

    @pytest.mark.asyncio
    async def test_tags_stay_editable_on_worn_outfits(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        shirt = _make_item(test_user.id)
        await _persist(db_session, shirt)

        created = await client.post(
            "/api/v1/outfits/studio",
            json={
                "items": [str(shirt.id)],
                "occasion": "casual",
                "scheduled_for": date.today().isoformat(),
                "mark_worn": True,
            },
            headers=auth_headers,
        )
        assert created.status_code == 201

        response = await client.patch(
            f"/api/v1/outfits/{created.json()['id']}",
            json={"tags": ["favourite"]},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["tags"] == ["favourite"]


class TestSuggestionsOnCreate:
    @pytest.mark.asyncio
    async def test_studio_lookbook_outfit_gets_suggestions(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        shirt = _make_item(test_user.id, "t-shirt", ["spring", "summer"])
        jeans = _make_item(test_user.id, "jeans", ["all-season"])
        await _persist(db_session, shirt, jeans)

        response = await client.post(
            "/api/v1/outfits/studio",
            json={
                "items": [str(shirt.id), str(jeans.id)],
                "occasion": "casual",
                "name": "Spring casual",
                "tags": ["Office"],
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["tags"] == ["office"]
        assert data["seasons"] == ["spring", "summer"]
        assert data["weather_tags"] == ["warm", "mild"]

    @pytest.mark.asyncio
    async def test_explicit_empty_seasons_are_kept(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        shirt = _make_item(test_user.id, "t-shirt", ["summer"])
        await _persist(db_session, shirt)

        response = await client.post(
            "/api/v1/outfits/studio",
            json={"items": [str(shirt.id)], "occasion": "casual", "name": "x", "seasons": []},
            headers=auth_headers,
        )

        assert response.status_code == 201
        assert response.json()["seasons"] == []

    @pytest.mark.asyncio
    async def test_dated_studio_outfit_gets_no_suggestions(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        shirt = _make_item(test_user.id, "t-shirt", ["summer"])
        await _persist(db_session, shirt)

        response = await client.post(
            "/api/v1/outfits/studio",
            json={
                "items": [str(shirt.id)],
                "occasion": "casual",
                "scheduled_for": date.today().isoformat(),
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        assert response.json()["seasons"] == []
        assert response.json()["weather_tags"] == []

    @pytest.mark.asyncio
    async def test_clone_to_lookbook_suggests_and_keeps_tags(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        coat = _make_item(test_user.id, "coat", ["winter"])
        await _persist(db_session, coat)
        worn = _make_outfit(test_user.id, is_lookbook=False, tags=["work"], items=[coat])
        await _persist(db_session, worn)

        response = await client.post(
            f"/api/v1/outfits/{worn.id}/clone-to-lookbook",
            json={"name": "Winter commute"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["scheduled_for"] is None
        assert data["tags"] == ["work"]
        assert data["seasons"] == ["winter"]
        assert data["weather_tags"] == ["cold"]


class TestBulkDeleteWithLookbookFilters:
    @pytest.mark.asyncio
    async def test_select_all_respects_tag_filter(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        tagged = _make_outfit(test_user.id, tags=["work"])
        untagged = _make_outfit(test_user.id, tags=["gym"])
        await _persist(db_session, tagged, untagged)

        response = await client.post(
            "/api/v1/outfits/bulk/delete",
            json={"select_all": True, "filters": {"is_lookbook": True, "tags": ["Work"]}},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["deleted"] == 1
        remaining = await db_session.execute(select(Outfit.id).where(Outfit.user_id == test_user.id))
        assert set(remaining.scalars().all()) == {untagged.id}
