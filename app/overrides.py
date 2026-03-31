import json
import os
from app.models import PhraseItem, Scene
from app.config import BASE_DIR


OVERRIDES_PATH = os.path.join(BASE_DIR, "data", "phrase_overrides.json")


def normalize_phrase_key(phrase: str) -> str:
    text = phrase.strip().lower()
    if text and text[-1] not in ".!?":
        text += "."
    return text


def load_overrides() -> dict:
    if not os.path.exists(OVERRIDES_PATH):
        return {}

    with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_phrase_override(phrase: str) -> dict | None:
    overrides = load_overrides()
    key = normalize_phrase_key(phrase)
    return overrides.get(key)


def apply_override(phrase_item: PhraseItem, override_data: dict) -> PhraseItem:
    if "gloss_en" in override_data:
        phrase_item.gloss_en = override_data["gloss_en"]

    if "visual_type" in override_data:
        phrase_item.visual_type = override_data["visual_type"]

    if "teacher_review" in override_data:
        phrase_item.teacher_review = override_data["teacher_review"]

    if "scene" in override_data and override_data["scene"] is not None:
        phrase_item.scene = Scene(**override_data["scene"])

    if "image_prompt" in override_data:
        phrase_item.image_prompt = override_data["image_prompt"]

    return phrase_item