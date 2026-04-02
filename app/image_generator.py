import base64
import hashlib
import os
from typing import Iterable, Optional

from openai import OpenAI

from app.config import IMAGE_DIR, REFERENCE_ASSETS_DIR, STYLE_GUIDE_PATH

client = OpenAI()

# 🔁 bump this whenever you want to regenerate everything
CACHE_SCHEMA_VERSION = "v2"


# ---------------------------
# Helpers
# ---------------------------

def _normalize_phrase_key(text: str) -> str:
    text = text.strip().lower()
    if text and text[-1] not in ".!?":
        text += "."
    return text


def _read_style_guide() -> str:
    if not os.path.exists(STYLE_GUIDE_PATH):
        return ""

    with open(STYLE_GUIDE_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


def _default_reference_image_paths() -> list[str]:
    candidates = [
        os.path.join(REFERENCE_ASSETS_DIR, "main_character_front.png"),
        os.path.join(REFERENCE_ASSETS_DIR, "main_character_side.png"),
        os.path.join(REFERENCE_ASSETS_DIR, "style_reference.png"),
    ]
    return [p for p in candidates if os.path.exists(p)]


def _file_sha256(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _build_cache_key(
    phrase: str,
    character_description: Optional[str],
    reference_image_paths: list[str],
    model: str,
    size: str,
    output_format: str,
    input_fidelity: str,
) -> str:
    """
    Build a stable cache key based on semantic inputs (NOT prompt text).
    """
    hasher = hashlib.sha256()

    normalized_phrase = _normalize_phrase_key(phrase)
    style_guide = _read_style_guide()

    hasher.update(CACHE_SCHEMA_VERSION.encode())
    hasher.update(normalized_phrase.encode())
    hasher.update(style_guide.encode())
    hasher.update((character_description or "").encode())
    hasher.update(model.encode())
    hasher.update(size.encode())
    hasher.update(output_format.encode())
    hasher.update(input_fidelity.encode())

    # include reference image contents (important!)
    for path in sorted(reference_image_paths):
        hasher.update(path.encode())
        hasher.update(_file_sha256(path).encode())

    return hasher.hexdigest()


def _build_full_prompt(scene_prompt: str, character_description: Optional[str]) -> str:
    style_guide = _read_style_guide()

    parts = []

    if style_guide:
        parts.append(style_guide)

    if character_description:
        parts.append("Character details:")
        parts.append(character_description.strip())

    parts.append("Scene to create:")
    parts.append(scene_prompt.strip())

    return "\n\n".join(parts)


# ---------------------------
# Main function
# ---------------------------

def generate_image(
    phrase: str,
    scene_prompt: str,
    image_id: str,  # kept for compatibility (not used in filename)
    reference_image_paths: Optional[Iterable[str]] = None,
    character_description: Optional[str] = None,
    model: str = "gpt-image-1.5",
    size: str = "1024x1024",
    output_format: str = "png",
    input_fidelity: str = "high",
) -> str:
    """
    Generate a consistent image with caching.

    Key idea:
    Cache is based on PHRASE + STYLE + REFERENCES (not prompt text),
    so small prompt variations won't break caching.
    """

    os.makedirs(IMAGE_DIR, exist_ok=True)

    # Load references
    ref_paths = list(reference_image_paths) if reference_image_paths else _default_reference_image_paths()

    if not ref_paths:
        raise RuntimeError("No reference images found.")

    for p in ref_paths:
        if not os.path.exists(p):
            raise FileNotFoundError(f"Missing reference image: {p}")

    # Build cache key (🔑 key change vs previous version)
    cache_key = _build_cache_key(
        phrase=phrase,
        character_description=character_description,
        reference_image_paths=ref_paths,
        model=model,
        size=size,
        output_format=output_format,
        input_fidelity=input_fidelity,
    )

    output_ext = "png" if output_format == "png" else output_format
    output_path = os.path.join(IMAGE_DIR, f"{cache_key}.{output_ext}")

    # ✅ CACHE HIT
    if os.path.exists(output_path):
        print(f"  Reusing cached image: {output_path}")
        return output_path

    # Build final prompt (used for generation ONLY, not caching)
    final_prompt = _build_full_prompt(
        scene_prompt=scene_prompt,
        character_description=character_description,
    )

    # Generate image
    file_handles = []

    try:
        for path in ref_paths:
            file_handles.append(open(path, "rb"))

        result = client.images.edit(
            model=model,
            image=file_handles,
            prompt=final_prompt,
            input_fidelity=input_fidelity,
            size=size,
            output_format=output_format,
        )

        if not result.data or not result.data[0].b64_json:
            raise RuntimeError("No image returned from API.")

        image_bytes = base64.b64decode(result.data[0].b64_json)

        with open(output_path, "wb") as f:
            f.write(image_bytes)

        print(f"  Generated new image: {output_path}")

        return output_path

    except Exception as e:
        raise RuntimeError(f"Image generation failed: {e}") from e

    finally:
        for fh in file_handles:
            try:
                fh.close()
            except Exception:
                pass