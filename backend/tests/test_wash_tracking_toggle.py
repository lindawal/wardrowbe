from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.config import Settings
from app.models.item import ClothingItem, ItemStatus
from app.services.recommendation_service import RecommendationService
from app.workers.notifications import check_wash_reminders


def _item(user_id, item_type: str, needs_wash: bool) -> ClothingItem:
    return ClothingItem(
        user_id=user_id,
        type=item_type,
        image_path=f"test/{uuid4()}.jpg",
        status=ItemStatus.ready,
        needs_wash=needs_wash,
    )


class TestCandidateItems:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("enabled", "expected_types"),
        [(False, {"shirt", "jeans"}), (True, {"shirt"})],
    )
    async def test_unwashed_items_are_only_skipped_when_tracking_is_enabled(
        self, db_session, test_user, enabled, expected_types
    ):
        db_session.add_all(
            [_item(test_user.id, "shirt", needs_wash=False), _item(test_user.id, "jeans", needs_wash=True)]
        )
        await db_session.commit()

        with patch(
            "app.services.recommendation_service.get_settings",
            return_value=Settings(wash_tracking_enabled=enabled),
        ):
            items = await RecommendationService(db_session).get_candidate_items(
                user=test_user,
                weather=MagicMock(),
                occasion="casual",
                preferences=None,
                exclude_items=[],
            )

        assert {item.type for item in items} == expected_types


class TestWashReminders:
    @pytest.mark.asyncio
    async def test_skipped_before_touching_the_database_when_disabled(self):
        with patch(
            "app.workers.notifications.get_settings",
            return_value=Settings(wash_tracking_enabled=False),
        ):
            result = await check_wash_reminders({})

        assert result == {"notified": 0, "skipped": "disabled"}
