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
from app.jobs.utils import update_status


def process_document(input_path: str, output_filename: str = "result.docx", status_path=None):
    CHARACTER_DESCRIPTION = (
        "Recurring school-age character with dark curly shoulder-length hair, "
        "friendly expression, orange t-shirt, blue jeans, and simple shoes."
    )

    temp_files_to_delete = []

    # -------------------------
    # 1. Extract phrases
    # -------------------------
    update_status(status_path, progress=5, message="A analisar o documento...")

    phrases = extract_phrases_from_docx(input_path)

    if not phrases:
        raise RuntimeError("O documento não contém frases para processar.")

    # -------------------------
    # 2. Analyze phrases
    # -------------------------
    update_status(status_path, progress=10, message="A analisar as frases...")

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

        analysis.final_image_prompt = build_image_prompt(analysis)
        items.append(analysis)

    # -------------------------
    # 3. Generate images (PARALLEL)
    # -------------------------
    total = len(items)
    completed = 0

    update_status(status_path, progress=20, message="A gerar imagens...")

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
                image_path, is_temp_file = future.result()
                item.image_path = image_path

                if is_temp_file:
                    temp_files_to_delete.append(image_path)

            except Exception as e:
                print(f"[IMAGE ERROR] Falha na imagem para {item.original!r}: {e}")
                item.image_path = None

            completed += 1
            progress = 20 + int((completed / total) * 60)

            update_status(
                status_path,
                progress=progress,
                message=f"A gerar imagens ({completed}/{total})"
            )

    # Remove any items that failed image generation
    items = [item for item in items if item.image_path]

    if not items:
        raise RuntimeError("Não foi possível gerar nenhuma imagem para esta ficha.")

    # -------------------------
    # 4. Build document
    # -------------------------
    update_status(status_path, progress=85, message="A criar a ficha...")

    output_path = os.path.join(os.path.dirname(input_path), output_filename)

    build_docx(items, output_path)

    # -------------------------
    # 5. Cleanup temp files
    # -------------------------
    for temp_file in temp_files_to_delete:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                print(f"[TEMP CLEANUP] removed {temp_file}")
        except Exception as e:
            print(f"[TEMP CLEANUP ERROR] {temp_file}: {e}")

    update_status(status_path, progress=100, message="Concluído!")

    return output_path