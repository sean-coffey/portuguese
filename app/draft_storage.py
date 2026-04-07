import json
import os
import uuid
from datetime import datetime, timezone

from app.config import DATA_DIR
from app.draft_models import WorksheetDraft
from app.storage import use_s3, upload_file_to_s3, download_file_from_s3, s3_object_exists

DRAFTS_DIR = os.path.join(DATA_DIR, "drafts")
os.makedirs(DRAFTS_DIR, exist_ok=True)


def _local_draft_path(draft_id: str) -> str:
    return os.path.join(DRAFTS_DIR, f"{draft_id}.json")


def _s3_draft_key(draft_id: str) -> str:
    return f"drafts/{draft_id}/draft.json"


def create_empty_draft(
    title: str | None,
    source_type: str,
    original_input_text: str | None,
    worksheet_profile_name: str,
    style_profile_name: str,
    learner_profile,
    items,
) -> WorksheetDraft:
    draft_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    return WorksheetDraft(
        draft_id=draft_id,
        title=title,
        source_type=source_type,
        original_input_text=original_input_text,
        worksheet_profile_name=worksheet_profile_name,
        style_profile_name=style_profile_name,
        learner_profile=learner_profile,
        created_at=now,
        updated_at=now,
        items=items,
    )


def save_draft(draft: WorksheetDraft) -> WorksheetDraft:
    draft.updated_at = datetime.now(timezone.utc).isoformat()

    local_path = _local_draft_path(draft.draft_id)

    with open(local_path, "w", encoding="utf-8") as f:
        f.write(draft.model_dump_json(indent=2))

    if use_s3():
        upload_file_to_s3(local_path, _s3_draft_key(draft.draft_id))

    return draft


def load_draft(draft_id: str) -> WorksheetDraft:
    local_path = _local_draft_path(draft_id)

    if use_s3():
        s3_key = _s3_draft_key(draft_id)
        if s3_object_exists(s3_key):
            downloaded = download_file_from_s3(s3_key, suffix=".json")
            with open(downloaded, "r", encoding="utf-8") as f:
                data = json.load(f)
            return WorksheetDraft(**data)

    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Draft not found: {draft_id}")

    with open(local_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return WorksheetDraft(**data)


def list_local_drafts() -> list[WorksheetDraft]:
    drafts = []

    for filename in os.listdir(DRAFTS_DIR):
        if not filename.endswith(".json"):
            continue

        path = os.path.join(DRAFTS_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            drafts.append(WorksheetDraft(**data))

    drafts.sort(key=lambda d: d.updated_at, reverse=True)
    return drafts