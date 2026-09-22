"""Grounded outfit explanations.

Selection and explanation are two separate model calls on purpose. When one
response carries both the item numbers and the prose, a small model can pick
number 7 (a sweater) while writing about the bomber jacket it meant: the numbers
decide which images are shown, the prose describes what the model believed it
picked, and nothing can reconcile the two after the fact. Explaining only the
items that survived selection and body-slot deduplication means the text cannot
name a garment that is not in the outfit, because no other garment is in its
prompt.
"""

import json
import logging
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING

from app.models.item import ClothingItem
from app.utils.prompts import load_prompt

if TYPE_CHECKING:
    from app.services.ai_service import AIService
    from app.services.weather_service import WeatherData

logger = logging.getLogger(__name__)

EXPLANATION_PROMPT = load_prompt("outfit_explanation")

EXPLANATION_FIELDS = ("headline", "highlights", "styling_tip")
# Includes the legacy names older prompts used for the same prose.
_UNGROUNDED_FIELDS = (*EXPLANATION_FIELDS, "reasoning", "style_notes")


def describe_item(item: ClothingItem) -> str:
    parts = []

    item_type = item.type or "item"
    if item.subtype:
        parts.append(f"{item.subtype} ({item_type})")
    else:
        parts.append(item_type)

    if item.colors and len(item.colors) > 1:
        parts.append(f"colors: {', '.join(item.colors)}")
    elif item.primary_color:
        parts.append(item.primary_color)

    if item.pattern and item.pattern != "solid":
        parts.append(item.pattern)

    if item.material:
        parts.append(item.material)

    if item.formality:
        parts.append(item.formality)

    if item.name:
        parts.insert(0, f'"{item.name}"')

    return " | ".join(parts)


def _extract_json_object(text: str) -> dict | None:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

    return parsed if isinstance(parsed, dict) else None


def parse_explanation(content: str) -> dict | None:
    data = _extract_json_object(content)
    if data is None:
        return None

    def clean_str(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        return value.strip() or None

    raw_highlights = data.get("highlights")
    highlights = (
        [h.strip() for h in raw_highlights if isinstance(h, str) and h.strip()]
        if isinstance(raw_highlights, list)
        else []
    )
    explanation = {
        "headline": clean_str(data.get("headline")),
        "highlights": highlights,
        "styling_tip": clean_str(data.get("styling_tip")),
    }
    if not any(explanation.values()):
        return None
    return explanation


def strip_explanation(outfit_data: dict) -> None:
    """Drop any prose the selection call returned despite the prompt.

    It was written before the final item list existed, so it is exactly the
    ungrounded text this module exists to keep off the screen.
    """
    for field in _UNGROUNDED_FIELDS:
        outfit_data.pop(field, None)


async def explain_outfit(
    ai_service: "AIService",
    items: Sequence[ClothingItem],
    *,
    occasion: str | None = None,
    weather: "WeatherData | None" = None,
    time_of_day: str | None = None,
    focus_item: ClothingItem | None = None,
) -> dict | None:
    """Return headline, highlights and styling_tip for these exact items, or None.

    Never raises: the outfit has already been selected by the time this runs,
    and on slow local hardware that selection can have taken minutes. Losing
    the explanation is a far smaller failure than losing the outfit.
    """
    if not items:
        return None

    context_lines = []
    if occasion:
        context_lines.append(f"- Occasion: {occasion}")
    if time_of_day:
        context_lines.append(f"- Time of day: {time_of_day}")
    if weather is not None:
        context_lines.append(f"- Weather: {weather.temperature}°C, {weather.condition}")
    if focus_item is not None:
        context_lines.append(
            f"- Built around: {describe_item(focus_item)} - explain why the other pieces suit it"
        )
    if not context_lines:
        context_lines.append("- Everyday wear")

    prompt = EXPLANATION_PROMPT.format(
        context="\n".join(context_lines),
        items_text="\n".join(f"- {describe_item(item)}" for item in items),
    )

    try:
        content = await ai_service.generate_text(prompt)
    except Exception as e:
        logger.warning(f"Outfit explanation failed, saving outfit without it: {e}")
        return None

    explanation = parse_explanation(content)
    if explanation is None:
        logger.warning("Outfit explanation was not usable JSON, saving outfit without it")
    return explanation
