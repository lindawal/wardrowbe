from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.item import ClothingItem, ItemStatus
from app.models.outfit import Outfit, UserFeedback
from app.models.user import User
from app.services import image_service as image_service_module
from app.services.image_service import ImageService
from app.services.outfit_photo_service import OutfitPhotoService

PHOTO_ENDPOINT = "/api/v1/outfits/photo"


def _jpeg(size=(60, 80)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, (120, 80, 160)).save(buf, format="JPEG")
    return buf.getvalue()


def _form(**overrides) -> dict:
    return {"name": "Mirror look", "occasion": "casual", **overrides}


async def _upload(
    client: AsyncClient,
    headers: dict,
    *,
    data: dict | None = None,
    image: bytes | None = None,
    filename: str = "look.jpg",
    content_type: str = "image/jpeg",
):
    return await client.post(
        PHOTO_ENDPOINT,
        data=_form() if data is None else data,
        files={"image": (filename, _jpeg() if image is None else image, content_type)},
        headers=headers,
    )


def _user_files(user_id) -> list[Path]:
    folder = ImageService().storage_path / str(user_id)
    return sorted(folder.glob("*")) if folder.exists() else []


async def _stored_paths(db_session: AsyncSession, outfit_id: str) -> list[str]:
    row = (
        await db_session.execute(
            select(Outfit.photo_path, Outfit.photo_medium_path, Outfit.photo_thumbnail_path).where(
                Outfit.id == UUID(outfit_id)
            )
        )
    ).one()
    return list(row)


class TestCreatePhotoLook:
    @pytest.mark.asyncio
    async def test_creates_lookbook_entry_with_stored_photo(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        response = await _upload(
            client,
            auth_headers,
            data=_form(tags=["Work", "date night"], seasons=["winter"], weather_tags=["Cold"]),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["is_photo_look"] is True
        assert data["items"] == []
        assert data["scheduled_for"] is None
        assert data["source"] == "manual"
        assert data["tags"] == ["work", "date night"]
        assert data["seasons"] == ["winter"]
        assert data["weather_tags"] == ["cold"]
        assert data["photo_url"].startswith(f"/api/v1/images/{test_user.id}/")
        assert data["photo_medium_url"] and data["photo_thumbnail_url"]

        for path in await _stored_paths(db_session, data["id"]):
            assert ImageService().get_image_path(path).exists()

        feedback = await db_session.execute(
            select(UserFeedback).where(UserFeedback.outfit_id == UUID(data["id"]))
        )
        assert feedback.scalar_one_or_none() is None

        image_response = await client.get(data["photo_url"])
        assert image_response.status_code == 200

    @pytest.mark.asyncio
    async def test_appears_in_lookbook_filters_and_tag_counts(
        self, client: AsyncClient, auth_headers
    ):
        created = await _upload(
            client,
            auth_headers,
            data=_form(name="Mirror selfie", tags=["work"], seasons=["winter"], weather_tags=["cold"]),
        )
        outfit_id = created.json()["id"]

        listed = await client.get(
            "/api/v1/outfits?is_lookbook=true&tags=work&seasons=winter&weather_tags=cold&search=mirror",
            headers=auth_headers,
        )
        assert {o["id"] for o in listed.json()["outfits"]} == {outfit_id}

        tags = await client.get("/api/v1/outfits/lookbook/tags", headers=auth_headers)
        assert tags.json() == {"total": 1, "tags": [{"tag": "work", "count": 1}]}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "data",
        [
            {"occasion": "casual"},
            _form(name="   "),
            _form(occasion="moonwalk"),
            _form(seasons=["monsoon"]),
            _form(tags=[f"tag{i}" for i in range(11)]),
        ],
    )
    async def test_invalid_fields_are_rejected_before_storing(
        self, client: AsyncClient, test_user, auth_headers, data
    ):
        files_before = len(_user_files(test_user.id))

        response = await _upload(client, auth_headers, data=data)

        assert response.status_code == 422
        assert len(_user_files(test_user.id)) == files_before

    @pytest.mark.asyncio
    async def test_rejects_unreadable_images(self, client: AsyncClient, auth_headers):
        garbage = await _upload(client, auth_headers, image=b"not an image")
        assert garbage.status_code == 400
        assert garbage.json()["detail"]["error_code"] == "PHOTO_INVALID"

        text = await _upload(
            client, auth_headers, image=b"hello", filename="evil.txt", content_type="text/plain"
        )
        assert text.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_images_above_the_megapixel_limit(
        self, client: AsyncClient, auth_headers, monkeypatch
    ):
        monkeypatch.setattr(image_service_module.settings, "max_image_megapixels", 0.001)

        response = await _upload(client, auth_headers)

        assert response.status_code == 413
        assert response.json()["detail"]["error_code"] == "PHOTO_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_failed_commit_removes_stored_files(self, db_session: AsyncSession):
        uid = uuid4()
        # Never persisted, so the outfit's user foreign key makes the commit fail.
        ghost = User(
            id=uid,
            external_id=f"ghost-{uid}",
            email=f"ghost-{uid}@example.com",
            display_name="Ghost",
            is_active=True,
        )

        with pytest.raises(Exception):
            await OutfitPhotoService(db_session).create_photo_look(
                user=ghost,
                image_data=_jpeg(),
                content_type="image/jpeg",
                filename="look.jpg",
                name="Ghost look",
                occasion="casual",
            )

        assert _user_files(uid) == []

    @pytest.mark.asyncio
    async def test_blocked_by_studio_kill_switch(
        self, client: AsyncClient, auth_headers, monkeypatch
    ):
        monkeypatch.setattr(get_settings(), "studio_disabled", True)

        response = await _upload(client, auth_headers)

        assert response.status_code == 503


class TestPhotoLookCleanupAndGuards:
    @pytest.mark.asyncio
    async def test_delete_removes_photo_files(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        outfit_id = (await _upload(client, auth_headers)).json()["id"]
        paths = await _stored_paths(db_session, outfit_id)

        response = await client.delete(f"/api/v1/outfits/{outfit_id}", headers=auth_headers)

        assert response.status_code == 204
        assert not any(ImageService().get_image_path(p).exists() for p in paths)

    @pytest.mark.asyncio
    async def test_bulk_delete_removes_photo_files(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        outfit_id = (await _upload(client, auth_headers)).json()["id"]
        paths = await _stored_paths(db_session, outfit_id)

        response = await client.post(
            "/api/v1/outfits/bulk/delete", json={"outfit_ids": [outfit_id]}, headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["deleted"] == 1
        assert not any(ImageService().get_image_path(p).exists() for p in paths)

    @pytest.mark.asyncio
    async def test_item_based_actions_are_rejected_but_labels_stay_editable(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        outfit_id = (await _upload(client, auth_headers)).json()["id"]

        wear = await client.post(
            f"/api/v1/outfits/{outfit_id}/wear-today", json={}, headers=auth_headers
        )
        assert wear.status_code == 400
        assert wear.json()["detail"]["error_code"] == "OUTFIT_IS_PHOTO_LOOK"

        clone = await client.post(
            f"/api/v1/outfits/{outfit_id}/clone-to-lookbook",
            json={"name": "Copy"},
            headers=auth_headers,
        )
        assert clone.status_code == 400

        item = ClothingItem(
            user_id=test_user.id,
            type="shirt",
            image_path=f"test/{uuid4()}.jpg",
            status=ItemStatus.ready,
        )
        db_session.add(item)
        await db_session.commit()

        items_patch = await client.patch(
            f"/api/v1/outfits/{outfit_id}", json={"items": [str(item.id)]}, headers=auth_headers
        )
        assert items_patch.status_code == 400

        tags_patch = await client.patch(
            f"/api/v1/outfits/{outfit_id}", json={"tags": ["Favourite"]}, headers=auth_headers
        )
        assert tags_patch.status_code == 200
        assert tags_patch.json()["tags"] == ["favourite"]
