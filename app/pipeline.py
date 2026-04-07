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
from app.worksheet_profiles import get_worksheet_profile
from app.style_profiles import load_style_profile
from app.question_builder import build_question_for_item, QuestionBatchContext
from app.config import USE_LLM_QUESTION_REFINEMENT
from app.draft_models import LearnerProfile, WorksheetDraft, WorksheetDraftItem
from app.doc_builder import build_subtitle_from_learner_profile, build_instructions_for_profile


def process_document(
    input_path: str,
    output_filename: str = "result.docx",
    worksheet_profile_name: str = "image_with_lines",
    style_profile_name: str = "default",
    learner_profile=None,
    status_path=None,
):

    worksheet_profile = get_worksheet_profile(worksheet_profile_name)
    style_profile = load_style_profile(style_profile_name)
    question_batch_context = QuestionBatchContext()

    if learner_profile is None:
        learner_profile = LearnerProfile()

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

        if worksheet_profile.include_question and worksheet_profile.question_mode:
            question_pt, answer_pt, exercise_family = build_question_for_item(
                analysis,
                worksheet_profile.question_mode,
                learner_profile=learner_profile,
                batch_context=question_batch_context,
            )
            analysis.question_pt = question_pt
            analysis.answer_pt = answer_pt
            analysis.exercise_type = exercise_family

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
                    reference_image_paths=[str(p) for p in style_profile.reference_image_paths],
                    character_description=style_profile.character_description,
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

    build_docx(
        items=items,
        output_path=output_path,
        worksheet_profile=worksheet_profile,
    )

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


def process_draft(
    draft: WorksheetDraft,
    output_path: str,
    status_path=None,
):
    worksheet_profile = get_worksheet_profile(draft.worksheet_profile_name)
    style_profile = load_style_profile(draft.style_profile_name)
    learner_profile = draft.learner_profile

    temp_files_to_delete = []

    # Only included items
    items = [item for item in draft.items if item.include_item]

    if not items:
        raise RuntimeError("O rascunho não contém itens selecionados para incluir.")

    update_status(status_path, progress=10, message="A preparar o rascunho...")

    # Prepare PhraseItem-like objects for generation/doc building
    prepared_items = []

    for item in items:
        phrase_item = PhraseItem(
            id=item.item_id,
            original=item.original,
            normalized=item.normalized,
            gloss_en=item.gloss_en,
            lexical_type=item.lexical_type,
            visual_type=item.visual_type,
            teacher_review=item.teacher_review,
            image_prompt="",
        )

        # Use teacher-approved question if present
        phrase_item.question_pt = item.selected_question_pt or item.suggested_question_pt
        phrase_item.exercise_type = item.selected_exercise_family or item.suggested_exercise_family

        # Rebuild image prompt from current analysis-like data
        phrase_item.final_image_prompt = build_image_prompt(phrase_item)

        prepared_items.append(phrase_item)

    total = len(prepared_items)
    completed = 0

    update_status(status_path, progress=20, message="A gerar imagens...")

    def image_task(item):
        return generate_image(
            phrase=item.normalized,
            scene_prompt=item.final_image_prompt,
            image_id=item.id,
            reference_image_paths=[str(p) for p in style_profile.reference_image_paths],
            character_description=style_profile.character_description,
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(image_task, item): item for item in prepared_items}

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

    prepared_items = [item for item in prepared_items if item.image_path]

    if not prepared_items:
        raise RuntimeError("Não foi possível gerar nenhuma imagem para esta ficha.")

    update_status(status_path, progress=85, message="A criar a ficha...")

    subtitle = build_subtitle_from_learner_profile(draft.learner_profile)
    instructions = build_instructions_for_profile(worksheet_profile)

    build_docx(
        items=prepared_items,
        output_path=output_path,
        worksheet_profile=worksheet_profile,
        title=draft.title,
        subtitle=subtitle,
        instructions=instructions,
    )

    for temp_file in temp_files_to_delete:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                print(f"[TEMP CLEANUP] removed {temp_file}")
        except Exception as e:
            print(f"[TEMP CLEANUP ERROR] {temp_file}: {e}")

    update_status(status_path, progress=100, message="Concluído!")
    return output_path