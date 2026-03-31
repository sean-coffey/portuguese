import uuid
from app.parser import extract_phrases_from_docx
from app.analyzer import analyze_phrase
from app.prompt_builder import build_image_prompt
from app.image_generator import generate_image
from app.doc_builder import build_docx
from app.overrides import get_phrase_override
from app.models import PhraseItem, Scene


def process_document(input_path: str, output_filename: str = "result.docx"):
    phrases = extract_phrases_from_docx(input_path)
    items = []

    CHARACTER_DESCRIPTION = (
        "Recurring school-age character with dark curly shoulder-length hair, "
        "friendly expression, orange t-shirt, blue jeans, and simple shoes."
    )

    for phrase in phrases:
        print(f"Processing: {phrase}")

        override = get_phrase_override(phrase)

        if override:
            print("  Using override without analyzer")
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

        final_prompt = build_image_prompt(analysis)

        print(f"  Final prompt: {final_prompt}")

        analysis.final_image_prompt = final_prompt

        try:
            image_path = generate_image(
                scene_prompt=analysis.final_image_prompt,
                image_id=analysis.id,
                character_description=CHARACTER_DESCRIPTION,
            )
            analysis.image_path = image_path
            items.append(analysis)
        except Exception as e:
            print(f"  Skipping phrase due to image error: {e}")

    if not items:
        raise RuntimeError("No worksheet items were generated successfully.")

    output_path = build_docx(items, filename=output_filename)
    return output_path