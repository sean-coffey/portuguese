from pydantic import BaseModel, Field
from typing import Optional, Literal


class Scene(BaseModel):
    subject: Optional[str] = Field(
        default=None,
        description="Who or what is the main subject in the scene."
    )
    action: Optional[str] = Field(
        default=None,
        description="The main action being shown, if any."
    )
    object: Optional[str] = Field(
        default=None,
        description="The main object receiving the action, if any."
    )
    setting: Optional[str] = Field(
        default=None,
        description="The location or setting of the scene, if relevant."
    )


class AnalyzerOutput(BaseModel):
    gloss_en: str = Field(
        description="A short, natural, literal English gloss of the Portuguese phrase."
    )
    input_type: Literal["word", "phrase", "sentence"] = Field(
        description="Whether the Portuguese input is a single word, a phrase, or a sentence."
    )
    lexical_type: Optional[Literal["noun", "verb", "adjective", "other"]] = Field(
        default=None,
        description="Best guess lexical class for single-word inputs."
    )
    visual_type: Literal[
        "literal_visual",
        "literal_but_ambiguous",
        "abstract",
        "idiomatic",
        "non_visual"
    ] = Field(
        description="How visually representable the phrase is for a learner."
    )
    teacher_review: bool = Field(
        description="True if a teacher should review the image because the phrase may be ambiguous, abstract, or idiomatic."
    )
    scene: Scene = Field(
        description="Structured description of the literal scene to show."
    )
    image_prompt: str = Field(
        description=(
            "A child-friendly educational illustration prompt that shows the meaning clearly, "
            "with simple background and no text."
        )
    )
    keyword_pt: Optional[str] = Field(
        default=None,
        description="Most teachable Portuguese keyword from the input."
    )
    verb_pt: Optional[str] = Field(
        default=None,
        description="Main Portuguese verb if clearly identifiable."
    )
    focus_phrase_pt: Optional[str] = Field(
        default=None,
        description="Short Portuguese chunk useful for classroom focus."
    )
    pedagogical_target: Optional[Literal[
        "vocabulary",
        "verb",
        "noun",
        "meaning",
        "description",
        "grammar",
        "other"
    ]] = Field(
        default=None,
        description="Best classroom focus for a simple worksheet question."
    )

    main_verb_infinitive_pt: Optional[str] = Field(
        default=None,
        description="Main Portuguese verb in infinitive form, if clear."
    )
    main_verb_surface_pt: Optional[str] = Field(
        default=None,
        description="Main Portuguese verb exactly as it appears in the input, if clear."
    )
    subject_pt: Optional[str] = Field(
        default=None,
        description="Main subject in Portuguese, if clear."
    )
    number_pt: Optional[Literal["singular", "plural"]] = Field(
        default=None,
        description="Number of the main subject, if clear."
    )
    tense_pt: Optional[str] = Field(
        default=None,
        description="Main tense in Portuguese, if clear, e.g. presente."
    )

class QuestionOutput(BaseModel):
    question_pt: str
    answer_pt: Optional[str] = None
    exercise_family: Optional[str] = None


class PhraseItem(BaseModel):
    id: str
    original: str
    normalized: str
    gloss_en: Optional[str] = None
    input_type: Optional[str] = None
    lexical_type: Optional[str] = None
    visual_type: Optional[str] = None
    teacher_review: bool = False
    scene: Optional[Scene] = None
    image_prompt: str
    final_image_prompt: Optional[str] = None
    image_path: Optional[str] = None

    keyword_pt: Optional[str] = None
    verb_pt: Optional[str] = None
    focus_phrase_pt: Optional[str] = None
    pedagogical_target: Optional[str] = None

    main_verb_infinitive_pt: Optional[str] = None
    main_verb_surface_pt: Optional[str] = None
    subject_pt: Optional[str] = None
    number_pt: Optional[str] = None
    tense_pt: Optional[str] = None

    question_pt: Optional[str] = None
    answer_pt: Optional[str] = None
    exercise_type: Optional[str] = None