import base64
import os
from pathlib import Path
from typing import Iterable, Optional

from openai import OpenAI

from app.config import IMAGE_DIR, REFERENCE_ASSETS_DIR, STYLE_GUIDE_PATH

client = OpenAI()


def _read_style_guide() -> str:
    if not os.path.exists(STYLE_GUIDE_PATH):
        return ""
    with open(STYLE_GUIDE_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


def _default_reference_image_paths() -> list[str]:
    """
    Returns reference images in a stable order.
    Add/remove files here as your character pack evolves.
    """
    candidates = [
        os.path.join(REFERENCE_ASSETS_DIR, "main_character_front.png"),
        os.path.join(REFERENCE_ASSETS_DIR, "main_character_side.png"),
        os.path.join(REFERENCE_ASSETS_DIR, "style_reference.png"),
    ]
    return [path for path in candidates if os.path.exists(path)]


def _build_full_prompt(scene_prompt: str, character_description: Optional[str] = None) -> str:
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
    scene_prompt: str,
    image_id: str,
    reference_image_paths: Optional[Iterable[str]] = None,
    character_description: Optional[str] = None,
    model: str = "gpt-image-1.5",
    size: str = "1024x1024",
    output_format: str = "png",
    input_fidelity: str = "high",
) -> str:
    """
    Generate a style-consistent image using reference images plus a persistent style guide.

    scene_prompt:
        The per-image scene instruction from your prompt builder.
    image_id:
        Filename stem for the saved output image.
    reference_image_paths:
        Optional explicit list of reference images.
        If omitted, uses files from reference_assets/.
    character_description:
        Optional repeated textual description of the recurring character.
    """

    os.makedirs(IMAGE_DIR, exist_ok=True)
    output_path = os.path.join(IMAGE_DIR, f"{image_id}.png")

    final_prompt = _build_full_prompt(
        scene_prompt=scene_prompt,
        character_description=character_description,
    )

    ref_paths = list(reference_image_paths) if reference_image_paths else _default_reference_image_paths()
    if not ref_paths:
        raise RuntimeError(
            "No reference images found. Add files under reference_assets/ "
            "or pass reference_image_paths explicitly."
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

        image_base64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)

        with open(output_path, "wb") as f:
            f.write(image_bytes)

        return output_path

    except Exception as e:
        raise RuntimeError(f"Image generation failed for {image_id}: {e}") from e

    finally:
        for fh in file_handles:
            try:
                fh.close()
            except Exception:
                pass