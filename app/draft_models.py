from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


CefrLevel = Literal["A1", "A2", "B1", "B2"]


class LearnerProfile(BaseModel):
    cefr_level: CefrLevel = "A1"
    age_min: Optional[int] = None
    age_max: Optional[int] = None


class WorksheetDraftItem(BaseModel):
    item_id: str

    original: str
    normalized: str

    gloss_en: Optional[str] = None
    lexical_type: Optional[str] = None
    visual_type: Optional[str] = None
    teacher_review: bool = False

    suggested_exercise_family: Optional[str] = None
    selected_exercise_family: Optional[str] = None

    suggested_question_pt: Optional[str] = None
    selected_question_pt: Optional[str] = None

    include_item: bool = True
    include_portuguese: Optional[bool] = None
    include_english_gloss: Optional[bool] = None
    include_question: Optional[bool] = None

    blank_lines_count: Optional[int] = None

    image_status: Optional[str] = None
    image_path: Optional[str] = None

    allowed_exercise_families: list[str] = Field(default_factory=list)


class WorksheetDraft(BaseModel):
    draft_id: str
    title: Optional[str] = None

    source_type: str  # "docx", "txt", "pasted", "mixed"
    original_input_text: Optional[str] = None

    worksheet_profile_name: str = "pt_only"
    style_profile_name: str = "default"

    learner_profile: LearnerProfile = Field(default_factory=LearnerProfile)

    include_portuguese_default: bool = True
    include_english_gloss_default: bool = False
    include_question_default: bool = False

    status: str = "draft"  # "draft", "ready", "generated"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    items: list[WorksheetDraftItem] = Field(default_factory=list)