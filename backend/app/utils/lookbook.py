"""Vocabulary and normalization for lookbook outfit attributes.

Writes go through the strict ``normalize_*`` functions (invalid input is a validation
error); list filters use the lenient ``parse_csv_*`` functions (invalid values are dropped).
"""

from collections.abc import Iterable

LOOKBOOK_SEASONS = ("spring", "summer", "fall", "winter")
WEATHER_TAGS = ("warm", "mild", "cold", "rain", "snow")
MAX_TAGS = 10
MAX_TAG_LENGTH = 30

_SEASON_ALIASES = {"autumn": "fall"}
_ALL_SEASON_VALUES = {"all-season", "all season", "all-seasons", "all"}


def _clean(raw: str) -> str:
    return " ".join(raw.split()).lower()


def _in_order(values: set[str], vocabulary: tuple[str, ...]) -> list[str]:
    return [v for v in vocabulary if v in values]


def _expand_season(raw: str) -> list[str]:
    value = _clean(raw)
    if value in _ALL_SEASON_VALUES:
        return list(LOOKBOOK_SEASONS)
    value = _SEASON_ALIASES.get(value, value)
    return [value] if value else []


def normalize_tag(raw: str) -> str | None:
    return _clean(raw) or None


def normalize_tags(raw: Iterable[str]) -> list[str]:
    tags: list[str] = []
    for value in raw:
        tag = normalize_tag(value)
        if tag is None:
            continue
        if len(tag) > MAX_TAG_LENGTH:
            raise ValueError(f"Tags must be at most {MAX_TAG_LENGTH} characters")
        # Tags travel comma-separated in list filters.
        if "," in tag:
            raise ValueError("Tags must not contain commas")
        if tag not in tags:
            tags.append(tag)
    if len(tags) > MAX_TAGS:
        raise ValueError(f"At most {MAX_TAGS} tags per outfit")
    return tags


def coerce_seasons(raw: Iterable[str]) -> list[str]:
    """Canonical seasons from free-form values, silently dropping unknown ones."""
    seasons = {s for value in raw for s in _expand_season(value) if s in LOOKBOOK_SEASONS}
    return _in_order(seasons, LOOKBOOK_SEASONS)


def normalize_seasons(raw: Iterable[str]) -> list[str]:
    values = list(raw)
    for value in values:
        for season in _expand_season(value):
            if season not in LOOKBOOK_SEASONS:
                raise ValueError(
                    f"Unknown season '{season}'. Must be one of: {', '.join(LOOKBOOK_SEASONS)}"
                )
    return coerce_seasons(values)


def coerce_weather_tags(raw: Iterable[str]) -> list[str]:
    return _in_order({_clean(v) for v in raw} & set(WEATHER_TAGS), WEATHER_TAGS)


def normalize_weather_tags(raw: Iterable[str]) -> list[str]:
    values = list(raw)
    for value in values:
        cleaned = _clean(value)
        if cleaned and cleaned not in WEATHER_TAGS:
            raise ValueError(
                f"Unknown weather tag '{cleaned}'. Must be one of: {', '.join(WEATHER_TAGS)}"
            )
    return coerce_weather_tags(values)


def parse_csv_tags(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    tags: list[str] = []
    for value in raw.split(","):
        tag = normalize_tag(value)
        if tag and len(tag) <= MAX_TAG_LENGTH and tag not in tags:
            tags.append(tag)
    return tags or None


def parse_csv_seasons(raw: str | None) -> list[str] | None:
    return (coerce_seasons(raw.split(",")) or None) if raw else None


def parse_csv_weather_tags(raw: str | None) -> list[str] | None:
    return (coerce_weather_tags(raw.split(",")) or None) if raw else None
