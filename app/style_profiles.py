import json
from dataclasses import dataclass
from pathlib import Path


STYLES_DIR = Path(__file__).resolve().parent.parent / "styles"


@dataclass(frozen=True)
class StyleProfile:
    name: str
    label_pt: str

    style_dir: Path
    style_guide_path: Path
    reference_image_paths: list[Path]

    character_description: str


def load_style_profile(style_name: str) -> StyleProfile:
    style_dir = STYLES_DIR / style_name
    config_path = style_dir / "config.json"
    style_guide_path = style_dir / "style_guide.txt"

    if not style_dir.exists():
        raise ValueError(f"Unknown style profile: {style_name}")

    if not config_path.exists():
        raise RuntimeError(f"Missing config.json for style profile: {style_name}")

    if not style_guide_path.exists():
        raise RuntimeError(f"Missing style_guide.txt for style profile: {style_name}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    reference_image_paths = [
        style_dir / filename
        for filename in data.get("reference_images", [])
    ]

    return StyleProfile(
        name=data["name"],
        label_pt=data["label_pt"],
        style_dir=style_dir,
        style_guide_path=style_guide_path,
        reference_image_paths=reference_image_paths,
        character_description=data.get("character_description", ""),
    )


def list_style_profiles() -> list[StyleProfile]:
    profiles = []

    if not STYLES_DIR.exists():
        return profiles

    for child in STYLES_DIR.iterdir():
        if child.is_dir() and (child / "config.json").exists():
            profiles.append(load_style_profile(child.name))

    return profiles