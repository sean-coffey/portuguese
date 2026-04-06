import base64
import hashlib
import os
from typing import Iterable, Optional

from openai import OpenAI

from app.config import IMAGE_DIR, REFERENCE_ASSETS_DIR, STYLE_GUIDE_PATH
from app.storage import use_s3, upload_file_to_s3, s3_object_exists, download_file_from_s3

client = OpenAI()

CACHE_SCHEMA_VERSION = "v4"


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


def generate_image(
    phrase: str,
    scene_prompt: str,
    image_id: str,  # kept for compatibility
    reference_image_paths: Optional[Iterable[str]] = None,
    character_description: Optional[str] = None,
    model: str = "gpt-image-1.5",
    size: str = "1024x1024",
    output_format: str = "png",
    input_fidelity: str = "high",
) -> tuple[str, bool]:
    """
    Returns:
        (image_path, is_temp_file)

    is_temp_file=True means the file was downloaded from S3 cache to a temporary
    local path and should be deleted later after the DOCX is built.
    """
    del image_id  # not used in hashed-filename mode

    os.makedirs(IMAGE_DIR, exist_ok=True)

    ref_paths = list(reference_image_paths) if reference_image_paths else _default_reference_image_paths()

    if not ref_paths:
        raise RuntimeError("No reference images found.")

    for p in ref_paths:
        if not os.path.exists(p):
            raise FileNotFoundError(f"Missing reference image: {p}")

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
    filename = f"{cache_key}.{output_ext}"
    local_output_path = os.path.join(IMAGE_DIR, filename)
    s3_key = f"cached-images/{filename}"

    # -------------------------
    # CLOUD CACHE (S3)
    # -------------------------
    if use_s3():
        if s3_object_exists(s3_key):
            print(f"[CACHE HIT S3] {s3_key}")
            downloaded_path = download_file_from_s3(s3_key, suffix=f".{output_ext}")
            return downloaded_path, True

    # -------------------------
    # LOCAL CACHE
    # -------------------------
    if os.path.exists(local_output_path):
        print(f"[CACHE HIT LOCAL] {local_output_path}")
        return local_output_path, False

    print(f"[CACHE MISS] generating image for phrase: {phrase}")

    final_prompt = _build_full_prompt(
        scene_prompt=scene_prompt,
        character_description=character_description,
    )

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

        with open(local_output_path, "wb") as f:
            f.write(image_bytes)

        if use_s3():
            upload_file_to_s3(local_output_path, s3_key)
            print(f"[CACHE STORE S3] {s3_key}")

        print(f"[IMAGE GENERATED] {local_output_path}")
        return local_output_path, False

    except Exception as e:
        print(f"[IMAGE ERROR] phrase={phrase!r} error={e}")
        raise RuntimeError(f"Image generation failed for phrase '{phrase}'.") from e

    finally:
        for fh in file_handles:
            try:
                fh.close()
            except Exception:
                pass