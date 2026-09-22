from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models.item import ClothingItem, ItemStatus
from app.models.learning import (
    ItemPairScore,
    OutfitPerformance,
    StyleInsight,
    UserLearningProfile,
)
from app.models.outfit import Outfit, OutfitSource, OutfitStatus, UserFeedback
from app.models.user import User
from app.services.learning_service import LearningService

EVERYTHING_ONCE = {
    "feedback": 2,
    "rejected": 1,
    "pair_scores": 1,
    "outfit_performances": 1,
    "insights": 1,
    "profiles": 1,
}


async def _seed(db, user: User) -> dict:
    shirt = ClothingItem(
        user_id=user.id, type="shirt", image_path=f"t/{uuid4()}.jpg", status=ItemStatus.ready
    )
    jeans = ClothingItem(
        user_id=user.id, type="jeans", image_path=f"t/{uuid4()}.jpg", status=ItemStatus.ready
    )
    db.add_all([shirt, jeans])
    await db.flush()

    def outfit(status: OutfitStatus) -> Outfit:
        return Outfit(
            user_id=user.id,
            occasion="casual",
            scheduled_for=date.today(),
            status=status,
            source=OutfitSource.on_demand,
        )

    rejected, accepted = outfit(OutfitStatus.rejected), outfit(OutfitStatus.accepted)
    db.add_all([rejected, accepted])
    await db.flush()

    low, high = sorted([shirt.id, jeans.id])
    db.add_all(
        [
            UserFeedback(outfit_id=rejected.id, rating=1),
            UserFeedback(outfit_id=accepted.id, rating=5),
            ItemPairScore(user_id=user.id, item1_id=low, item2_id=high, times_paired=2),
            OutfitPerformance(outfit_id=accepted.id, user_id=user.id, occasion="casual"),
            StyleInsight(
                user_id=user.id,
                category="color",
                insight_type="pattern",
                title="Likes navy",
                description="Navy shows up in accepted outfits.",
            ),
            UserLearningProfile(user_id=user.id),
        ]
    )
    await db.commit()
    return {"rejected": rejected.id, "accepted": accepted.id}


async def _remaining(db, user: User) -> dict:
    # Read before expire_all: an expired attribute reloads synchronously, which
    # an AsyncSession refuses.
    user_id = user.id
    db.expire_all()
    outfit_ids = select(Outfit.id).where(Outfit.user_id == user_id)

    async def count(model, clause):
        return await db.scalar(select(func.count()).select_from(model).where(clause))

    return {
        "feedback": await count(UserFeedback, UserFeedback.outfit_id.in_(outfit_ids)),
        "rejected": await count(
            Outfit, (Outfit.user_id == user_id) & (Outfit.status == OutfitStatus.rejected)
        ),
        "pair_scores": await count(ItemPairScore, ItemPairScore.user_id == user_id),
        "outfit_performances": await count(OutfitPerformance, OutfitPerformance.user_id == user_id),
        "insights": await count(StyleInsight, StyleInsight.user_id == user_id),
        "profiles": await count(UserLearningProfile, UserLearningProfile.user_id == user_id),
    }


@pytest.fixture
async def other_user(db_session) -> User:
    uid = uuid4()
    user = User(
        id=uid,
        external_id=f"other-{uid}",
        email=f"other-{uid}@example.com",
        display_name="Other",
        timezone="UTC",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


class TestResetLearning:
    @pytest.mark.asyncio
    async def test_clears_ratings_and_everything_derived(self, db_session, test_user):
        ids = await _seed(db_session, test_user)
        user_id = test_user.id

        counts = await LearningService(db_session).reset_learning(user_id)

        assert counts == EVERYTHING_ONCE
        assert await _remaining(db_session, test_user) == dict.fromkeys(EVERYTHING_ONCE, 0)

        statuses = dict(
            (
                await db_session.execute(
                    select(Outfit.id, Outfit.status).where(Outfit.user_id == user_id)
                )
            ).all()
        )
        # Kept in the history, but no longer a negative signal or a same-day exclusion.
        assert statuses[ids["rejected"]] == OutfitStatus.skipped
        # The user's outfit history, not a rating.
        assert statuses[ids["accepted"]] == OutfitStatus.accepted

    @pytest.mark.asyncio
    async def test_leaves_other_users_untouched(self, db_session, test_user, other_user):
        await _seed(db_session, test_user)
        await _seed(db_session, other_user)

        await LearningService(db_session).reset_learning(test_user.id)

        assert await _remaining(db_session, other_user) == EVERYTHING_ONCE

    @pytest.mark.asyncio
    async def test_nothing_to_reset_reports_zeros(self, db_session, test_user):
        counts = await LearningService(db_session).reset_learning(test_user.id)

        assert counts == dict.fromkeys(EVERYTHING_ONCE, 0)


class TestResetEndpoint:
    @pytest.mark.asyncio
    async def test_reset_then_learning_page_still_loads(
        self, client, auth_headers, db_session, test_user
    ):
        await _seed(db_session, test_user)

        response = await client.post("/api/v1/learning/reset", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == EVERYTHING_ONCE

        # The profile row is gone; the page must fall back to "no data", not fail.
        learning = await client.get("/api/v1/learning", headers=auth_headers)
        assert learning.status_code == 200
        assert learning.json()["profile"]["has_learning_data"] is False
