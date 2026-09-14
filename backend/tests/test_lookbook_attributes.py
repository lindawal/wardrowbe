import pytest
from pydantic import ValidationError

from app.models.item import ClothingItem
from app.schemas.outfit import LookbookAttributeFields
from app.services.lookbook_suggestions import suggest_seasons, suggest_weather_tags
from app.utils.lookbook import (
    LOOKBOOK_SEASONS,
    normalize_seasons,
    normalize_tags,
    normalize_weather_tags,
    parse_csv_seasons,
    parse_csv_tags,
    parse_csv_weather_tags,
)


def _item(item_type="shirt", season=None, tags=None, material=None, subtype=None) -> ClothingItem:
    return ClothingItem(
        type=item_type,
        season=season or [],
        tags=tags or {},
        material=material,
        subtype=subtype,
    )


class TestSuggestSeasons:
    def test_intersects_item_seasons(self):
        items = [
            _item("t-shirt", ["spring", "summer"]),
            _item("jeans", ["all-season"]),
            _item("sneakers", ["spring", "summer", "fall"]),
        ]
        assert suggest_seasons(items) == ["spring", "summer"]

    def test_normalizes_autumn(self):
        assert suggest_seasons([_item(season=["Autumn"])]) == ["fall"]

    def test_falls_back_to_item_tag_seasons(self):
        assert suggest_seasons([_item(tags={"season": ["winter"]})]) == ["winter"]

    def test_ignores_items_without_season_data(self):
        items = [_item("shirt", ["summer"]), _item("belt")]
        assert suggest_seasons(items) == ["summer"]

    def test_no_data_returns_empty(self):
        assert suggest_seasons([_item(), _item("jeans")]) == []

    def test_no_data_uses_legacy_season(self):
        assert suggest_seasons([_item()], legacy_season="Summer") == ["summer"]
        assert suggest_seasons([], legacy_season="all-season") == list(LOOKBOOK_SEASONS)

    def test_conflict_keeps_majority(self):
        items = [
            _item("coat", ["winter"]),
            _item("sweater", ["fall", "winter"]),
            _item("shirt", ["summer"]),
        ]
        assert suggest_seasons(items) == ["winter"]

    def test_conflict_without_majority_is_empty(self):
        assert suggest_seasons([_item(season=["summer"]), _item(season=["winter"])]) == []


class TestSuggestWeatherTags:
    def test_maps_seasons_to_temperature(self):
        assert suggest_weather_tags([_item()], ["summer"]) == ["warm"]
        assert suggest_weather_tags([_item()], ["spring", "fall"]) == ["mild"]
        assert suggest_weather_tags([_item()], ["winter"]) == ["cold"]

    def test_no_seasons_and_plain_items_is_empty(self):
        assert suggest_weather_tags([_item()], []) == []

    def test_heavy_layer_forces_cold(self):
        assert suggest_weather_tags([_item("coat")], ["summer"]) == ["cold"]
        assert suggest_weather_tags([_item("sweater", material="Wool")], ["fall"]) == [
            "mild",
            "cold",
        ]
        assert suggest_weather_tags([_item("jacket", subtype="puffer")], []) == ["cold"]

    def test_hot_only_items_force_warm(self):
        assert suggest_weather_tags([_item("shorts")], ["spring", "winter"]) == ["warm", "mild"]

    def test_never_suggests_rain_or_snow(self):
        items = [
            _item("jacket", subtype="raincoat", material="waterproof"),
            _item("boots", tags={"features": ["snow-proof", "water-resistant"]}),
        ]
        weather = suggest_weather_tags(items, list(LOOKBOOK_SEASONS))
        assert "rain" not in weather
        assert "snow" not in weather


class TestNormalization:
    def test_tags_are_trimmed_lowercased_and_deduplicated(self):
        assert normalize_tags(["  Büro ", "büro", "Date   Night", "", "  "]) == [
            "büro",
            "date night",
        ]

    def test_empty_tag_list_is_kept(self):
        assert normalize_tags([]) == []

    def test_tag_limits(self):
        with pytest.raises(ValueError):
            normalize_tags(["work,gym"])
        with pytest.raises(ValueError):
            normalize_tags(["x" * 31])
        assert normalize_tags(["x" * 30]) == ["x" * 30]
        with pytest.raises(ValueError):
            normalize_tags([f"tag{i}" for i in range(11)])

    def test_seasons(self):
        assert normalize_seasons(["Winter", "autumn"]) == ["fall", "winter"]
        assert normalize_seasons(["all-season"]) == list(LOOKBOOK_SEASONS)
        with pytest.raises(ValueError):
            normalize_seasons(["monsoon"])

    def test_weather_tags(self):
        assert normalize_weather_tags(["Rain", "warm", "rain"]) == ["warm", "rain"]
        with pytest.raises(ValueError):
            normalize_weather_tags(["foggy"])

    def test_csv_filters_drop_invalid_values(self):
        assert parse_csv_tags("Work, gym,,work") == ["work", "gym"]
        assert parse_csv_tags(None) is None
        assert parse_csv_seasons("summer,bogus") == ["summer"]
        assert parse_csv_weather_tags("bogus") is None


class TestLookbookAttributeFields:
    def test_none_means_unchanged_and_empty_list_clears(self):
        fields = LookbookAttributeFields(tags=[], seasons=None)
        assert fields.tags == []
        assert fields.seasons is None
        assert fields.weather_tags is None

    def test_validates_through_normalizers(self):
        fields = LookbookAttributeFields(tags=["A", "a"], weather_tags=["SNOW"])
        assert fields.tags == ["a"]
        assert fields.weather_tags == ["snow"]
        with pytest.raises(ValidationError):
            LookbookAttributeFields(seasons=["monsoon"])
