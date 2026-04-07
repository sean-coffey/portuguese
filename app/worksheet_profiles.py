from dataclasses import dataclass
from typing import Optional, Literal


WorksheetLayoutMode = Literal[
    "phrase_image",
    "image_with_lines",
    "question_answer",
    "glossary"
]

QuestionMode = Optional[Literal[
    "vocabulary",
    "grammar",
    "comprehension",
    "production"
]]


@dataclass(frozen=True)
class WorksheetProfile:
    name: str
    label_pt: str

    template_filename: str

    layout_mode: WorksheetLayoutMode

    include_portuguese: bool = True
    include_english_gloss: bool = False
    include_teacher_note: bool = False

    question_mode: QuestionMode = None
    include_question: bool = False

    blank_lines_count: int = 0


WORKSHEET_PROFILES: dict[str, WorksheetProfile] = {
    "pt_only": WorksheetProfile(
        name="pt_only",
        label_pt="Português + imagem",
        template_filename="worksheet_template.docx",
        layout_mode="phrase_image",
        include_portuguese=True,
        include_english_gloss=False,
        include_teacher_note=False,
        include_question=False,
        blank_lines_count=0,
    ),
    "pt_en": WorksheetProfile(
        name="pt_en",
        label_pt="Português + inglês + imagem",
        template_filename="worksheet_template.docx",
        layout_mode="phrase_image",
        include_portuguese=True,
        include_english_gloss=True,
        include_teacher_note=False,
        include_question=False,
        blank_lines_count=0,
    ),
    "image_with_lines": WorksheetProfile(
        name="image_with_lines",
        label_pt="Imagem com linhas para descrição",
        template_filename="describe_image_template.docx",
        layout_mode="image_with_lines",
        include_portuguese=False,
        include_english_gloss=False,
        include_teacher_note=False,
        include_question=True,
        question_mode="comprehension",
        blank_lines_count=4,
    ),
    "image_with_production": WorksheetProfile(
        name="image_with_production",
        label_pt="Imagem com produção escrita",
        template_filename="describe_image_template.docx",
        layout_mode="image_with_lines",
        include_portuguese=False,
        include_english_gloss=False,
        include_teacher_note=False,
        include_question=True,
        question_mode="production",
        blank_lines_count=4,
    ),
    "vocabulary_question": WorksheetProfile(
        name="vocabulary_question",
        label_pt="Imagem + pergunta de vocabulário",
        template_filename="worksheet_template.docx",
        layout_mode="question_answer",
        include_portuguese=True,
        include_english_gloss=False,
        include_teacher_note=False,
        include_question=True,
        question_mode="vocabulary",
        blank_lines_count=2,
    ),
    "grammar_question": WorksheetProfile(
        name="grammar_question",
        label_pt="Imagem + pergunta de gramática",
        template_filename="worksheet_template.docx",
        layout_mode="question_answer",
        include_portuguese=True,
        include_english_gloss=False,
        include_teacher_note=False,
        include_question=True,
        question_mode="grammar",
        blank_lines_count=2,
    ),
    "glossary": WorksheetProfile(
        name="glossary",
        label_pt="Glossário ilustrado",
        template_filename="glossary_template.docx",
        layout_mode="glossary",
        include_portuguese=True,
        include_english_gloss=True,
        include_teacher_note=False,
        include_question=False,
        blank_lines_count=0,
    ),
}


def get_worksheet_profile(profile_name: str) -> WorksheetProfile:
    try:
        return WORKSHEET_PROFILES[profile_name]
    except KeyError:
        raise ValueError(f"Unknown worksheet profile: {profile_name}")


def list_worksheet_profiles() -> list[WorksheetProfile]:
    return list(WORKSHEET_PROFILES.values())