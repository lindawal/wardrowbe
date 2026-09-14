#!/usr/bin/env python3
"""
Suggest seasons and weather tags for existing lookbook outfits that have neither.

Safe to re-run: outfits that already carry seasons or weather tags are skipped.

Usage:
    docker compose exec backend python scripts/backfill_lookbook_attributes.py --dry-run
    docker compose exec backend python scripts/backfill_lookbook_attributes.py
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload, sessionmaker

from app.config import get_settings
from app.models.outfit import Outfit, OutfitItem
from app.services.lookbook_suggestions import suggest_seasons, suggest_weather_tags


async def backfill(dry_run: bool) -> None:
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            select(Outfit)
            .where(
                and_(
                    Outfit.scheduled_for.is_(None),
                    func.cardinality(Outfit.seasons) == 0,
                    func.cardinality(Outfit.weather_tags) == 0,
                )
            )
            .options(selectinload(Outfit.items).selectinload(OutfitItem.item))
        )
        outfits = list(result.scalars().all())

        updated = 0
        for outfit in outfits:
            items = [oi.item for oi in outfit.items if oi.item is not None]
            seasons = suggest_seasons(items, outfit.season)
            weather_tags = suggest_weather_tags(items, seasons)
            if not seasons and not weather_tags:
                continue

            label = outfit.name or outfit.occasion
            print(f"{outfit.id} ({label}): seasons={seasons} weather_tags={weather_tags}")
            if not dry_run:
                outfit.seasons = seasons
                outfit.weather_tags = weather_tags
            updated += 1

        if not dry_run:
            await session.commit()

    await engine.dispose()
    verb = "Would update" if dry_run else "Updated"
    print(f"{verb} {updated} of {len(outfits)} lookbook outfits without seasons or weather tags")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show suggestions without saving")
    args = parser.parse_args()
    asyncio.run(backfill(args.dry_run))


if __name__ == "__main__":
    main()
