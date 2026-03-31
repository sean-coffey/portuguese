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