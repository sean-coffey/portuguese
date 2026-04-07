from pydantic import BaseModel, Field
from typing import Optional

from app.draft_models import LearnerProfile, WorksheetDraftItem


class CreateDraftFromTextRequest(BaseModel):
    text: str
    title: Optional[str] = None
    worksheet_profile_name: str = "pt_only"
    style_profile_name: str = "default"
    learner_profile: LearnerProfile = Field(default_factory=LearnerProfile)


class SaveDraftRequest(BaseModel):
    title: Optional[str] = None
    worksheet_profile_name: str = "pt_only"
    style_profile_name: str = "default"
    learner_profile: LearnerProfile = Field(default_factory=LearnerProfile)
    items: list[WorksheetDraftItem] = Field(default_factory=list)

class RegenerateQuestionRequest(BaseModel):
    selected_exercise_family: Optional[str] = None