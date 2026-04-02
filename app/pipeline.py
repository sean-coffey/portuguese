import uuid
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.parser import extract_phrases_from_docx
from app.analyzer import analyze_phrase
from app.prompt_builder import build_image_prompt
from app.image_generator import generate_image
from app.doc_builder import build_docx
from app.overrides import get_phrase_override
from app.models import PhraseItem, Scene

# NEW
from app.jobs.utils import update_status


def process_document(input_path: str, output_filename: str = "result.docx", status_path=None):
    CHARACTER_DESCRIPTION = (
        "Recurring school-age character with dark curly shoulder-length hair, "
        "friendly expression, orange t-shirt, blue jeans, and simple shoes."
    )

    # -------------------------
    # 1. Extract phrases
    # -------------------------
    update_status(status_path, progress=5, message="Parsing document")

    phrases = extract_phrases_from_docx(input_path)

    # -------------------------
    # 2. Analyze phrases
    # -------------------------
    update_status(status_path, progress=10, message="Analyzing phrases")

    items = []

    for phrase in phrases:
        override = get_phrase_override(phrase)

        if override:
            normalized = phrase.strip()
            if normalized and normalized[-1] not in ".!?":
                normalized += "."

            analysis = PhraseItem(
                id=str(uuid.uuid4()),
                original=phrase,
                normalized=normalized,
                gloss_en=override.get("gloss_en"),
                visual_type=override.get("visual_type"),
                teacher_review=override.get("teacher_review", False),
                scene=Scene(**override["scene"]) if override.get("scene") else None,
                image_prompt=override.get("image_prompt", ""),
            )
        else:
            analysis = analyze_phrase(phrase)

        # Build prompt
        analysis.final_image_prompt = build_image_prompt(analysis)

        items.append(analysis)

    # -------------------------
    # 3. Generate images (PARALLEL)
    # -------------------------
    total = len(items)
    completed = 0

    update_status(status_path, progress=20, message="Generating images...")

    def image_task(item):
        return generate_image(
            phrase=item.normalized,
            scene_prompt=item.final_image_prompt,
            image_id=item.id,
            character_description=CHARACTER_DESCRIPTION,
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(image_task, item): item for item in items}

        for future in as_completed(futures):
            item = futures[future]

            try:
                item.image_path = future.result()
            except Exception as e:
                print(f"Image failed for {item.original}: {e}")
                item.image_path = None  # or fallback

            completed += 1

            progress = 20 + int((completed / total) * 60)

            update_status(
                status_path,
                progress=progress,
                message=f"Generating images ({completed}/{total})"
            )

    # -------------------------
    # 4. Build document
    # -------------------------
    update_status(status_path, progress=85, message="Building document")

    output_path = os.path.join(os.path.dirname(input_path), output_filename)

    build_docx(items, output_path)

    update_status(status_path, progress=100, message="Done")

    return output_path