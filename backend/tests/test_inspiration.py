from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from arq import Retry
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.inspiration import InspirationLook, InspirationLookItem, InspirationStatus
from app.models.user import User
from app.services import image_service as image_service_module
from app.services.ai_service import AIService, ClothingTags
from app.services.image_service import ImageService
from app.workers.inspiration import analyze_inspiration_look
from app.workers.worker import WorkerSettings

INSPIRATION_ENDPOINT = "/api/v1/inspiration"


def _jpeg(size=(60, 80), color=(120, 80, 160)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


async def _upload_look(
    client: AsyncClient,
    headers: dict,
    *,
    image: bytes | None = None,
    filename: str = "look.jpg",
    content_type: str = "image/jpeg",
):
    with patch("app.api.inspiration.create_pool", new_callable=AsyncMock) as mock_create_pool:
        mock_redis = AsyncMock()
        mock_redis.enqueue_job.return_value.job_id = "fake-job-id"
        mock_create_pool.return_value = mock_redis
        response = await client.post(
            INSPIRATION_ENDPOINT,
            files={"image": (filename, _jpeg() if image is None else image, content_type)},
            headers=headers,
        )
    return response, mock_redis


async def _create_look_via_api(client: AsyncClient, headers: dict) -> dict:
    response, _ = await _upload_look(client, headers)
    assert response.status_code == 201
    return response.json()


async def _make_look_with_items(
    db_session: AsyncSession,
    user_id,
    items: list[dict] | None = None,
    created_at=None,
) -> InspirationLook:
    look = InspirationLook(
        user_id=user_id,
        photo_path=f"test/{uuid4()}.jpg",
        status=InspirationStatus.analyzed,
        **({"created_at": created_at} if created_at is not None else {}),
    )
    db_session.add(look)
    await db_session.flush()
    for i, data in enumerate(items or [{"type": "t-shirt", "primary_color": "black"}]):
        db_session.add(InspirationLookItem(inspiration_look_id=look.id, position=i, **data))
    await db_session.commit()
    return look


async def _get_first_item_id(db_session: AsyncSession, look_id) -> str:
    result = await db_session.execute(
        select(InspirationLookItem).where(InspirationLookItem.inspiration_look_id == look_id)
    )
    return result.scalar_one().id


class TestUploadInspirationLook:
    @pytest.mark.asyncio
    async def test_creates_pending_look_and_queues_analysis(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        response, mock_redis = await _upload_look(client, auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["photo_url"] and data["photo_medium_url"] and data["photo_thumbnail_url"]
        assert data["items"] == []

        mock_redis.enqueue_job.assert_called_once()
        args = mock_redis.enqueue_job.call_args
        assert args.args[0] == "analyze_inspiration_look"
        assert args.args[1] == data["id"]
        assert args.kwargs["_queue_name"] == "arq:tagging"

        for path in (
            (
                await db_session.execute(
                    select(
                        InspirationLook.photo_path,
                        InspirationLook.photo_medium_path,
                        InspirationLook.photo_thumbnail_path,
                    ).where(InspirationLook.id == data["id"])
                )
            )
            .one()
        ):
            assert ImageService().get_image_path(path).exists()

    @pytest.mark.asyncio
    async def test_rejects_unreadable_images(self, client: AsyncClient, auth_headers):
        response, _ = await _upload_look(client, auth_headers, image=b"not an image")

        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "PHOTO_INVALID"

    @pytest.mark.asyncio
    async def test_rejects_images_above_the_megapixel_limit(
        self, client: AsyncClient, auth_headers, monkeypatch
    ):
        monkeypatch.setattr(image_service_module.settings, "max_image_megapixels", 0.001)

        response, _ = await _upload_look(client, auth_headers)

        assert response.status_code == 413
        assert response.json()["detail"]["error_code"] == "PHOTO_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_blocked_when_ai_vision_disabled(
        self, client: AsyncClient, auth_headers, monkeypatch
    ):
        monkeypatch.setattr(get_settings(), "ai_internal_enabled", False)

        response, _ = await _upload_look(client, auth_headers)

        assert response.status_code == 503
        assert response.json()["detail"]["error_code"] == "AI_VISION_DISABLED"


class TestListInspirationLooks:
    @pytest.mark.asyncio
    async def test_returns_only_own_looks_newest_first(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
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
        await db_session.flush()
        await _make_look_with_items(db_session, other.id)

        first = await _make_look_with_items(
            db_session, test_user.id, created_at=datetime(2026, 1, 1, tzinfo=UTC)
        )
        second = await _make_look_with_items(
            db_session, test_user.id, created_at=datetime(2026, 1, 2, tzinfo=UTC)
        )

        response = await client.get(INSPIRATION_ENDPOINT, headers=auth_headers)

        assert response.status_code == 200
        ids = [look["id"] for look in response.json()["looks"]]
        assert ids == [str(second.id), str(first.id)]


class TestGetInspirationLook:
    @pytest.mark.asyncio
    async def test_returns_look_with_items(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look_with_items(
            db_session,
            test_user.id,
            items=[
                {"type": "t-shirt", "primary_color": "black", "description": "black t-shirt"},
                {"type": "jeans", "primary_color": "blue", "description": "blue jeans"},
            ],
        )

        response = await client.get(f"{INSPIRATION_ENDPOINT}/{look.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "analyzed"
        assert [i["type"] for i in data["items"]] == ["t-shirt", "jeans"]
        assert data["items"][0]["description"] == "black t-shirt"

    @pytest.mark.asyncio
    async def test_404_for_missing_look(self, client: AsyncClient, auth_headers):
        response = await client.get(f"{INSPIRATION_ENDPOINT}/{uuid4()}", headers=auth_headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_404_for_someone_elses_look(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
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
        await db_session.flush()
        look = await _make_look_with_items(db_session, other.id)

        response = await client.get(f"{INSPIRATION_ENDPOINT}/{look.id}", headers=auth_headers)
        assert response.status_code == 404


class TestUpdateInspirationLookItem:
    @pytest.mark.asyncio
    async def test_applies_valid_correction(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look_with_items(db_session, test_user.id)
        item_id = await _get_first_item_id(db_session, look.id)

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{item_id}",
            json={"type": "sweater", "primary_color": "gray", "fit": "oversized"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "sweater"
        assert data["primary_color"] == "gray"
        assert data["fit"] == "oversized"

    @pytest.mark.asyncio
    async def test_rejects_invalid_tag_value(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look_with_items(db_session, test_user.id)
        item_id = await _get_first_item_id(db_session, look.id)

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{item_id}",
            json={"primary_color": "chartreuse"},
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_type_cannot_be_cleared(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look_with_items(db_session, test_user.id)
        item_id = await _get_first_item_id(db_session, look.id)

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{item_id}",
            json={"type": None},
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_clearing_optional_field_to_null(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look_with_items(
            db_session, test_user.id, items=[{"type": "jacket", "primary_color": "navy"}]
        )
        item_id = await _get_first_item_id(db_session, look.id)

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{item_id}",
            json={"primary_color": None},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["primary_color"] is None

    @pytest.mark.asyncio
    async def test_404_for_missing_item(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look_with_items(db_session, test_user.id)

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{uuid4()}",
            json={"type": "sweater"},
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_400_when_no_fields_given(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look = await _make_look_with_items(db_session, test_user.id)
        item_id = await _get_first_item_id(db_session, look.id)

        response = await client.patch(
            f"{INSPIRATION_ENDPOINT}/{look.id}/items/{item_id}",
            json={},
            headers=auth_headers,
        )

        assert response.status_code == 400


class TestDeleteInspirationLook:
    @pytest.mark.asyncio
    async def test_removes_look_and_files(
        self, client: AsyncClient, auth_headers, test_user, db_session: AsyncSession
    ):
        look_data = await _create_look_via_api(client, auth_headers)
        row = (
            await db_session.execute(
                select(
                    InspirationLook.photo_path,
                    InspirationLook.photo_medium_path,
                    InspirationLook.photo_thumbnail_path,
                ).where(InspirationLook.id == look_data["id"])
            )
        ).one()
        paths = list(row)

        response = await client.delete(
            f"{INSPIRATION_ENDPOINT}/{look_data['id']}", headers=auth_headers
        )

        assert response.status_code == 204
        assert not any(ImageService().get_image_path(p).exists() for p in paths)
        remaining = await db_session.execute(
            select(InspirationLook).where(InspirationLook.id == look_data["id"])
        )
        assert remaining.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_404_for_missing_look(self, client: AsyncClient, auth_headers):
        response = await client.delete(f"{INSPIRATION_ENDPOINT}/{uuid4()}", headers=auth_headers)
        assert response.status_code == 404


class TestAnalyzeInspirationLookWorker:
    @pytest.mark.asyncio
    async def test_stores_items_ordered_by_position_and_marks_analyzed(
        self, db_session: AsyncSession, test_user
    ):
        look = InspirationLook(
            user_id=test_user.id,
            photo_path="test/look.jpg",
            status=InspirationStatus.pending,
        )
        db_session.add(look)
        await db_session.commit()

        returned_items = [
            ClothingTags(type="t-shirt", primary_color="black", description="black t-shirt"),
            ClothingTags(type="jeans", primary_color="blue", description="wide baggy jeans"),
            ClothingTags(type="sneakers", primary_color="white", description="white sneakers"),
        ]

        with (
            patch("app.workers.inspiration.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch.object(AIService, "analyze_outfit_look", new_callable=AsyncMock) as analyze,
        ):
            analyze.return_value = returned_items
            result = await analyze_inspiration_look({"job_try": 1}, str(look.id), __file__)

        assert result["status"] == "success"
        assert result["item_count"] == 3

        await db_session.refresh(look)
        assert look.status == InspirationStatus.analyzed

        stored = (
            await db_session.execute(
                select(InspirationLookItem)
                .where(InspirationLookItem.inspiration_look_id == look.id)
                .order_by(InspirationLookItem.position)
            )
        ).scalars().all()
        assert [i.type for i in stored] == ["t-shirt", "jeans", "sneakers"]
        assert [i.position for i in stored] == [0, 1, 2]
        assert stored[0].description == "black t-shirt"

    @pytest.mark.asyncio
    async def test_replaces_previous_items_on_reanalysis(self, db_session: AsyncSession, test_user):
        look = await _make_look_with_items(
            db_session, test_user.id, items=[{"type": "coat", "primary_color": "brown"}]
        )
        look.status = InspirationStatus.pending
        await db_session.commit()

        with (
            patch("app.workers.inspiration.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch.object(AIService, "analyze_outfit_look", new_callable=AsyncMock) as analyze,
        ):
            analyze.return_value = [ClothingTags(type="dress", primary_color="red")]
            await analyze_inspiration_look({"job_try": 1}, str(look.id), __file__)

        stored = (
            await db_session.execute(
                select(InspirationLookItem).where(InspirationLookItem.inspiration_look_id == look.id)
            )
        ).scalars().all()
        assert len(stored) == 1
        assert stored[0].type == "dress"

    @pytest.mark.asyncio
    async def test_vision_disabled_marks_error(self, db_session: AsyncSession, test_user, monkeypatch):
        look = InspirationLook(
            user_id=test_user.id,
            photo_path="test/look.jpg",
            status=InspirationStatus.pending,
        )
        db_session.add(look)
        await db_session.commit()

        monkeypatch.setattr(get_settings(), "ai_internal_enabled", False)

        with (
            patch("app.workers.inspiration.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            result = await analyze_inspiration_look({"job_try": 1}, str(look.id), __file__)

        assert result["status"] == "skipped"
        await db_session.refresh(look)
        assert look.status == InspirationStatus.error
        assert look.error_message == "AI vision is disabled"

    @pytest.mark.asyncio
    async def test_image_not_found_marks_error(self, db_session: AsyncSession, test_user):
        look = InspirationLook(
            user_id=test_user.id,
            photo_path="test/look.jpg",
            status=InspirationStatus.pending,
        )
        db_session.add(look)
        await db_session.commit()

        with (
            patch("app.workers.inspiration.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            result = await analyze_inspiration_look(
                {"job_try": 1}, str(look.id), "/nonexistent/path/look.jpg"
            )

        assert result["status"] == "error"
        await db_session.refresh(look)
        assert look.status == InspirationStatus.error

    @pytest.mark.asyncio
    async def test_reraises_and_retries_on_non_final_attempt(
        self, db_session: AsyncSession, test_user
    ):
        look = InspirationLook(
            user_id=test_user.id,
            photo_path="test/look.jpg",
            status=InspirationStatus.pending,
        )
        db_session.add(look)
        await db_session.commit()

        with (
            patch("app.workers.inspiration.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch.object(AIService, "analyze_outfit_look", new_callable=AsyncMock) as analyze,
        ):
            analyze.side_effect = RuntimeError("upstream 500")
            with pytest.raises(Retry):
                await analyze_inspiration_look({"job_try": 1}, str(look.id), __file__)

        await db_session.refresh(look)
        # Still analyzing: arq has retries left, so the look must not be
        # condemned until the final attempt is spent.
        assert look.status == InspirationStatus.analyzing

    @pytest.mark.asyncio
    async def test_marks_error_on_final_attempt(self, db_session: AsyncSession, test_user):
        look = InspirationLook(
            user_id=test_user.id,
            photo_path="test/look.jpg",
            status=InspirationStatus.pending,
        )
        db_session.add(look)
        await db_session.commit()

        with (
            patch("app.workers.inspiration.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch.object(AIService, "analyze_outfit_look", new_callable=AsyncMock) as analyze,
        ):
            analyze.side_effect = RuntimeError("upstream 500")
            with pytest.raises(RuntimeError):
                await analyze_inspiration_look(
                    {"job_try": WorkerSettings.max_tries}, str(look.id), __file__
                )

        await db_session.refresh(look)
        assert look.status == InspirationStatus.error
        assert "upstream 500" in look.error_message
