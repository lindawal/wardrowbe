"""Pydantic schemas for Step 1 (inspiration looks): upload + AI analysis with
manually-correctable tags. Reuses ClothingItem's tag vocabulary so values validate
consistently and (in Step 2) match cleanly against the wardrobe.
"""

from pydantic import BaseModel, Field, field_validator

from app.services.ai_service import (
    VALID_COLORS,
    VALID_FIT,
    VALID_FORMALITY,
    VALID_MATERIALS,
    VALID_PATTERNS,
    VALID_SEASONS,
    VALID_STYLES,
    VALID_TYPES,
)


def _validate_optional(value: str | None, valid_set: set[str], field: str) -> str | None:
    if value is None:
        return None
    normalized = value.lower().strip()
    if normalized not in valid_set:
        raise ValueError(f"invalid {field}: {value!r}")
    return normalized


def _validate_list(values: list[str] | None, valid_set: set[str], field: str) -> list[str]:
    if not values:
        return []
    normalized = [v.lower().strip() for v in values]
    invalid = [v for v in normalized if v not in valid_set]
    if invalid:
        raise ValueError(f"invalid {field} value(s): {invalid}")
    return normalized


class InspirationLookItemUpdate(BaseModel):
    """Manual correction of one AI-identified item within an inspiration look.

    Send only the fields the user actually edited (partial update, matched via
    exclude_unset). A scalar field explicitly set to null clears it; a list field
    explicitly set to null is treated as an empty list, since the column itself
    is never nullable. `type` cannot be cleared -- the model requires one.
    """

    type: str | None = None
    subtype: str | None = Field(None, max_length=50)
    primary_color: str | None = None
    colors: list[str] | None = None
    pattern: str | None = None
    material: str | None = None
    style: list[str] | None = None
    formality: str | None = None
    season: list[str] | None = None
    fit: str | None = None
    description: str | None = Field(None, max_length=200)

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v: str | None) -> str:
        if v is None:
            raise ValueError("type cannot be cleared")
        normalized = v.lower().strip()
        if normalized not in VALID_TYPES:
            raise ValueError(f"invalid type: {v!r}")
        return normalized

    @field_validator("primary_color")
    @classmethod
    def _validate_primary_color(cls, v: str | None) -> str | None:
        return _validate_optional(v, VALID_COLORS, "primary_color")

    @field_validator("pattern")
    @classmethod
    def _validate_pattern(cls, v: str | None) -> str | None:
        return _validate_optional(v, VALID_PATTERNS, "pattern")

    @field_validator("material")
    @classmethod
    def _validate_material(cls, v: str | None) -> str | None:
        return _validate_optional(v, VALID_MATERIALS, "material")

    @field_validator("formality")
    @classmethod
    def _validate_formality(cls, v: str | None) -> str | None:
        return _validate_optional(v, VALID_FORMALITY, "formality")

    @field_validator("fit")
    @classmethod
    def _validate_fit(cls, v: str | None) -> str | None:
        return _validate_optional(v, VALID_FIT, "fit")

    @field_validator("colors")
    @classmethod
    def _validate_colors(cls, v: list[str] | None) -> list[str]:
        return _validate_list(v, VALID_COLORS, "colors")

    @field_validator("style")
    @classmethod
    def _validate_style(cls, v: list[str] | None) -> list[str]:
        return _validate_list(v, VALID_STYLES, "style")

    @field_validator("season")
    @classmethod
    def _validate_season(cls, v: list[str] | None) -> list[str]:
        return _validate_list(v, VALID_SEASONS, "season")


class InspirationLookItemCreate(InspirationLookItemUpdate):
    """A piece added by hand (one the AI missed). Only `type` is required; every
    other tag uses the same vocabulary and validation as a correction."""

    type: str
