from io import BytesIO
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import ClothingItem, ItemStatus
from app.models.outfit import Outfit, OutfitItem, OutfitSource, OutfitStatus
from app.models.user import User
from app.services import image_service as image_service_module
from app.config import get_settings
from app.services.image_service import ImageService
from app.services.outfit_photo_service import OutfitPhotoService

PHOTO_LOOK_ENDPOINT = "/api/v1/outfits/photo"


def _jpeg(size=(60, 80), color=(120, 80, 160)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def _make_item(user_id, item_type="t-shirt", **kwargs) -> ClothingItem:
    return ClothingItem(
        user_id=user_id,
        type=item_type,
        image_path=f"test/{uuid4()}.jpg",
        status=ItemStatus.ready,
        **kwargs,
    )


def _make_outfit(user_id, items: list[ClothingItem]) -> Outfit:
    outfit = Outfit(
        user_id=user_id,
        occasion="casual",
        status=OutfitStatus.accepted,
        source=OutfitSource.manual,
    )
    for i, item in enumerate(items):
        outfit.items.append(OutfitItem(item_id=item.id, position=i))
    return outfit


async def _upload_worn_photo(
    client: AsyncClient,
    headers: dict,
    outfit_id,
    *,
    image: bytes | None = None,
    filename: str = "worn.jpg",
    content_type: str = "image/jpeg",
):
    return await client.post(
        f"/api/v1/outfits/{outfit_id}/worn-photo",
        files={"image": (filename, _jpeg() if image is None else image, content_type)},
        headers=headers,
    )


async def _stored_worn_paths(db_session: AsyncSession, outfit_id: str) -> list[str]:
    row = (
        await db_session.execute(
            select(
                Outfit.worn_photo_path,
                Outfit.worn_photo_medium_path,
                Outfit.worn_photo_thumbnail_path,
            ).where(Outfit.id == UUID(outfit_id))
        )
    ).one()
    return list(row)


class TestUploadWornPhoto:
    @pytest.mark.asyncio
    async def test_attaches_photo_to_item_based_outfit(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()
        outfit = _make_outfit(test_user.id, [item])
        db_session.add(outfit)
        await db_session.commit()
        await db_session.refresh(outfit)

        response = await _upload_worn_photo(client, auth_headers, outfit.id)

        assert response.status_code == 200
        data = response.json()
        assert data["worn_photo_url"] and data["worn_photo_medium_url"]
        assert data["worn_photo_thumbnail_url"]
        # Items stay untouched -- a worn photo is additional, not a replacement.
        assert len(data["items"]) == 1
        assert data["is_photo_look"] is False

        for path in await _stored_worn_paths(db_session, str(outfit.id)):
            assert ImageService().get_image_path(path).exists()

    @pytest.mark.asyncio
    async def test_replacing_worn_photo_removes_old_files(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()
        outfit = _make_outfit(test_user.id, [item])
        db_session.add(outfit)
        await db_session.commit()
        await db_session.refresh(outfit)

        first = await _upload_worn_photo(client, auth_headers, outfit.id)
        old_paths = await _stored_worn_paths(db_session, str(outfit.id))

        second = await _upload_worn_photo(client, auth_headers, outfit.id, image=_jpeg(color=(10, 200, 10)))
        assert second.status_code == 200
        new_paths = await _stored_worn_paths(db_session, str(outfit.id))

        assert old_paths != new_paths
        assert not any(ImageService().get_image_path(p).exists() for p in old_paths)
        assert all(ImageService().get_image_path(p).exists() for p in new_paths)
        assert first.json()["worn_photo_url"] != second.json()["worn_photo_url"]

    @pytest.mark.asyncio
    async def test_rejected_for_photo_looks(self, client: AsyncClient, auth_headers):
        photo_look = await client.post(
            PHOTO_LOOK_ENDPOINT,
            data={"name": "Mirror look", "occasion": "casual"},
            files={"image": ("look.jpg", _jpeg(), "image/jpeg")},
            headers=auth_headers,
        )
        outfit_id = photo_look.json()["id"]

        response = await _upload_worn_photo(client, auth_headers, outfit_id)

        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "OUTFIT_IS_PHOTO_LOOK"

    @pytest.mark.asyncio
    async def test_rejects_unreadable_images(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()
        outfit = _make_outfit(test_user.id, [item])
        db_session.add(outfit)
        await db_session.commit()
        await db_session.refresh(outfit)

        response = await _upload_worn_photo(client, auth_headers, outfit.id, image=b"not an image")

        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "PHOTO_INVALID"

    @pytest.mark.asyncio
    async def test_rejects_images_above_the_megapixel_limit(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession, monkeypatch
    ):
        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()
        outfit = _make_outfit(test_user.id, [item])
        db_session.add(outfit)
        await db_session.commit()
        await db_session.refresh(outfit)

        monkeypatch.setattr(image_service_module.settings, "max_image_megapixels", 0.001)

        response = await _upload_worn_photo(client, auth_headers, outfit.id)

        assert response.status_code == 413
        assert response.json()["detail"]["error_code"] == "PHOTO_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_404_for_missing_outfit(self, client: AsyncClient, auth_headers):
        response = await _upload_worn_photo(client, auth_headers, uuid4())
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_blocked_by_studio_kill_switch(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession, monkeypatch
    ):
        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()
        outfit = _make_outfit(test_user.id, [item])
        db_session.add(outfit)
        await db_session.commit()
        await db_session.refresh(outfit)

        monkeypatch.setattr(get_settings(), "studio_disabled", True)

        response = await _upload_worn_photo(client, auth_headers, outfit.id)

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_404_for_someone_elses_outfit(
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
        item = _make_item(other.id)
        db_session.add(item)
        await db_session.flush()
        outfit = _make_outfit(other.id, [item])
        db_session.add(outfit)
        await db_session.commit()
        await db_session.refresh(outfit)

        response = await _upload_worn_photo(client, auth_headers, outfit.id)

        assert response.status_code == 404


class TestDeleteWornPhoto:
    @pytest.mark.asyncio
    async def test_removes_worn_photo_and_files(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()
        outfit = _make_outfit(test_user.id, [item])
        db_session.add(outfit)
        await db_session.commit()
        await db_session.refresh(outfit)

        await _upload_worn_photo(client, auth_headers, outfit.id)
        paths = await _stored_worn_paths(db_session, str(outfit.id))

        response = await client.delete(
            f"/api/v1/outfits/{outfit.id}/worn-photo", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["worn_photo_url"] is None
        assert data["worn_photo_medium_url"] is None
        assert data["worn_photo_thumbnail_url"] is None
        assert not any(ImageService().get_image_path(p).exists() for p in paths)
        # The outfit itself (and its items) survives -- only the photo is gone.
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_is_a_noop_when_no_worn_photo_exists(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()
        outfit = _make_outfit(test_user.id, [item])
        db_session.add(outfit)
        await db_session.commit()
        await db_session.refresh(outfit)

        response = await client.delete(
            f"/api/v1/outfits/{outfit.id}/worn-photo", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["worn_photo_url"] is None

    @pytest.mark.asyncio
    async def test_404_for_missing_outfit(self, client: AsyncClient, auth_headers):
        response = await client.delete(
            f"/api/v1/outfits/{uuid4()}/worn-photo", headers=auth_headers
        )
        assert response.status_code == 404


class TestOutfitDeleteCleansUpWornPhoto:
    @pytest.mark.asyncio
    async def test_deleting_outfit_removes_worn_photo_files(
        self, client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
    ):
        item = _make_item(test_user.id)
        db_session.add(item)
        await db_session.flush()
        outfit = _make_outfit(test_user.id, [item])
        db_session.add(outfit)
        await db_session.commit()
        await db_session.refresh(outfit)

        await _upload_worn_photo(client, auth_headers, outfit.id)
        paths = await _stored_worn_paths(db_session, str(outfit.id))

        response = await client.delete(f"/api/v1/outfits/{outfit.id}", headers=auth_headers)

        assert response.status_code == 204
        assert not any(ImageService().get_image_path(p).exists() for p in paths)


class TestFailedCommitCleanup:
    @pytest.mark.asyncio
    async def test_failed_commit_removes_newly_stored_file(self, db_session: AsyncSession):
        uid = uuid4()
        ghost = User(
            id=uid,
            external_id=f"ghost-{uid}",
            email=f"ghost-{uid}@example.com",
            display_name="Ghost",
            is_active=True,
        )
        # Added but never flushed: the outfit's user_id foreign key doesn't exist,
        # so the commit inside set_worn_photo (an INSERT, since this row was never
        # persisted) fails.
        outfit = Outfit(
            id=uuid4(),
            user_id=uid,
            occasion="casual",
            status=OutfitStatus.accepted,
            source=OutfitSource.manual,
        )
        db_session.add(outfit)

        with pytest.raises(Exception):
            await OutfitPhotoService(db_session).set_worn_photo(
                user=ghost,
                outfit=outfit,
                image_data=_jpeg(),
                content_type="image/jpeg",
                filename="worn.jpg",
            )

        folder = ImageService().storage_path / str(uid)
        assert not folder.exists() or list(folder.glob("*")) == []
