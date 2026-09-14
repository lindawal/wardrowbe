"""Suggest seasons and weather tags for a lookbook outfit from its clothing items.

Only warm/mild/cold are ever suggested; rain and snow are left to the user because the
item vocabulary does not describe weather protection reliably.
"""

from collections import Counter
from collections.abc import Iterable

from app.models.item import ClothingItem
from app.services.item_scorer import (
    HEAVY_LAYER_MATERIALS,
    HEAVY_LAYER_SUBTYPES,
    HEAVY_LAYER_TYPES,
)
from app.utils.lookbook import LOOKBOOK_SEASONS, WEATHER_TAGS, coerce_seasons

SEASON_WEATHER = {"summer": "warm", "spring": "mild", "fall": "mild", "winter": "cold"}
# Mirrors the hot-weather-only types penalised in item_scorer._temp_bucket_score.
HOT_ONLY_TYPES = {"shorts", "tank-top", "sandals"}


def _item_seasons(item: ClothingItem) -> set[str]:
    raw = item.season or (item.tags or {}).get("season") or []
    if isinstance(raw, str):
        raw = [raw]
    return set(coerce_seasons(raw))


def _is_heavy_layer(item: ClothingItem) -> bool:
    return (
        (item.type or "").lower() in HEAVY_LAYER_TYPES
        or (item.material or "").lower() in HEAVY_LAYER_MATERIALS
        or (item.subtype or "").lower() in HEAVY_LAYER_SUBTYPES
    )


def suggest_seasons(items: Iterable[ClothingItem], legacy_season: str | None = None) -> list[str]:
    per_item = [seasons for seasons in (_item_seasons(item) for item in items) if seasons]
    if not per_item:
        return coerce_seasons([legacy_season]) if legacy_season else []

    common = set.intersection(*per_item)
    if not common:
        # Layered outfits often have no season every piece shares; keep the majority view.
        counts = Counter(season for seasons in per_item for season in seasons)
        common = {season for season, n in counts.items() if n > len(per_item) / 2}
    return [s for s in LOOKBOOK_SEASONS if s in common]


def suggest_weather_tags(items: Iterable[ClothingItem], seasons: Iterable[str]) -> list[str]:
    items = list(items)
    weather = {SEASON_WEATHER[s] for s in seasons if s in SEASON_WEATHER}
    if any(_is_heavy_layer(item) for item in items):
        weather.add("cold")
        weather.discard("warm")
    elif any((item.type or "").lower() in HOT_ONLY_TYPES for item in items):
        weather.add("warm")
        weather.discard("cold")
    return [w for w in WEATHER_TAGS if w in weather]
