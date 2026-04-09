# app/api.py

import os
import uuid
import shutil
import json
import threading
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.auth import (
    COOKIE_NAME,
    create_session_value,
    credentials_are_valid,
    require_login,
    is_logged_in,
)
from app.pipeline import process_document, process_draft
from app.jobs.utils import update_status
from app.config import BASE_DIR
from app.storage import use_s3, upload_file_to_s3, generate_download_url
from app.rate_limit import is_rate_limited

from app.api_models import CreateDraftFromTextRequest, SaveDraftRequest, RegenerateQuestionRequest
from app.draft_models import WorksheetDraftItem, LearnerProfile
from app.draft_storage import create_empty_draft, save_draft, load_draft, list_local_drafts
from app.analyzer import analyze_phrase
from app.question_builder import build_question_for_item, QuestionBatchContext, build_question_from_family, get_allowed_families_for_item
from app.worksheet_profiles import get_worksheet_profile

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

JOBS_DIR = os.path.join(BASE_DIR, "data", "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)


def create_job_dir():
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    return job_id, job_dir


def build_draft_items_from_lines(
    lines: list[str],
    worksheet_profile_name: str,
    learner_profile: LearnerProfile,
):
    items = []
    worksheet_profile = get_worksheet_profile(worksheet_profile_name)
    question_batch_context = QuestionBatchContext()

    for line in lines:
        text = line.strip()
        if not text:
            continue

        analysis = analyze_phrase(text)

        allowed_families = get_allowed_families_for_item(
            analysis,
            learner_profile=learner_profile,
        )

        suggested_exercise_family = None
        selected_exercise_family = None
        suggested_question_pt = None
        selected_question_pt = None

        if worksheet_profile.include_question and worksheet_profile.question_mode:
            question_pt, answer_pt, exercise_family = build_question_for_item(
                analysis,
                worksheet_profile.question_mode,
                learner_profile=learner_profile,
                batch_context=question_batch_context,
            )

            suggested_exercise_family = exercise_family
            selected_exercise_family = exercise_family

            suggested_question_pt = question_pt
            selected_question_pt = question_pt

        draft_item = WorksheetDraftItem(
            item_id=analysis.id,
            original=analysis.original,
            normalized=analysis.normalized,
            gloss_en=analysis.gloss_en,
            lexical_type=analysis.lexical_type,
            visual_type=analysis.visual_type,
            teacher_review=analysis.teacher_review,
            suggested_exercise_family=suggested_exercise_family,
            selected_exercise_family=selected_exercise_family,
            suggested_question_pt=suggested_question_pt,
            selected_question_pt=selected_question_pt,
            include_item=True,
            allowed_exercise_families=allowed_families,
        )

        items.append(draft_item)

    return items


def process_job(input_path, output_path, status_path, worksheet_profile_name="pt_only", style_profile_name="default"):
    try:
        update_status(status_path, status="processing", progress=0, message="A iniciar...")

        local_output_path = process_document(
            input_path=input_path,
            output_filename=os.path.basename(output_path),
            worksheet_profile_name=worksheet_profile_name,
            style_profile_name=style_profile_name,
            status_path=status_path
        )

        s3_key = None

        if use_s3():
            job_id = os.path.basename(os.path.dirname(input_path))
            s3_key = f"worksheets/{job_id}/output.docx"

            upload_file_to_s3(local_output_path, s3_key)

        update_status(
            status_path,
            status="completed",
            progress=100,
            message="Concluído!",
            extra={"s3_key": s3_key} if s3_key else None
        )

    except Exception as e:
        update_status(
            status_path,
            status="failed",
            message="Ocorreu um erro ao gerar a ficha.",
            extra={"error": str(e)}
        )


def process_draft_job(draft_id: str, output_path: str, status_path: str):
    try:
        update_status(
            status_path,
            status="processing",
            progress=0,
            message="A iniciar..."
        )

        draft = load_draft(draft_id)

        local_output_path = process_draft(
            draft=draft,
            output_path=output_path,
            status_path=status_path,
        )

        s3_key = None

        if use_s3():
            job_id = os.path.basename(os.path.dirname(output_path))
            s3_key = f"worksheets/{job_id}/output.docx"
            upload_file_to_s3(local_output_path, s3_key)

        update_status(
            status_path,
            status="completed",
            progress=100,
            message="Concluído!",
            extra={"s3_key": s3_key} if s3_key else None
        )

    except Exception as e:
        print(f"[DRAFT GENERATE ERROR] {e}")

        update_status(
            status_path,
            status="failed",
            progress=100,
            message="Ocorreu um erro ao gerar a ficha.",
            extra={"error": str(e)}
        )


@app.get("/")
def serve_ui(request: Request):
    guard = require_login(request)
    if guard:
        return guard
    return FileResponse("app/static/index.html")


# ---------------------------
# Upload + process
# ---------------------------
@app.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    worksheet_profile: str = Form("pt_only"),
    style_profile: str = Form("default"),
):
    guard = require_login(request)
    if guard:
        return guard

    client_ip = request.client.host if request.client else "unknown"

    if is_rate_limited(client_ip):
        return JSONResponse(
            status_code=429,
            content={"error": "Demasiados pedidos. Tente novamente dentro de um minuto."}
        )

    if not file.filename.endswith(".docx"):
        return JSONResponse(
            status_code=400,
            content={"error": "Only .docx files are supported"}
        )

    job_id, job_dir = create_job_dir()
    input_path = os.path.join(job_dir, "input.docx")
    output_path = os.path.join(job_dir, "output.docx")
    status_path = os.path.join(job_dir, "status.json")

    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    update_status(status_path, status="processing", progress=0, message="A iniciar...")

    threading.Thread(
        target=process_job,
        args=(input_path, output_path, status_path, worksheet_profile, style_profile),
        daemon=True
    ).start()

    return {"job_id": job_id}


# ---------------------------
# Download result
# ---------------------------
@app.get("/download/{job_id}")
def download(request: Request, job_id: str):
    guard = require_login(request)
    if guard:
        return guard

    job_dir = os.path.join(JOBS_DIR, job_id)
    status_path = os.path.join(job_dir, "status.json")
    output_path = os.path.join(job_dir, "output.docx")

    if not os.path.exists(status_path):
        return JSONResponse(status_code=404, content={"error": "Job not found"})

    with open(status_path, "r", encoding="utf-8") as f:
        status = json.load(f)

    if use_s3():
        s3_key = status.get("s3_key")
        if not s3_key:
            return JSONResponse(status_code=404, content={"error": "Output not found in S3"})

        download_url = generate_download_url(s3_key)
        return RedirectResponse(download_url)

    if not os.path.exists(output_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="worksheet.docx"
    )


@app.get("/status/{job_id}")
def get_status(request: Request, job_id: str):
    guard = require_login(request)
    if guard:
        return guard

    status_path = os.path.join(JOBS_DIR, job_id, "status.json")

    if not os.path.exists(status_path):
        return {"status": "not_found"}

    with open(status_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_logged_in(request):
        return RedirectResponse(url="/", status_code=303)

    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Iniciar sessão</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: #f8f4ec;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
            }
            .card {
                background: white;
                padding: 32px;
                border-radius: 16px;
                box-shadow: 0 12px 30px rgba(0,0,0,0.12);
                width: 360px;
            }
            h1 {
                margin-top: 0;
                text-align: center;
            }
            label {
                display: block;
                margin-top: 12px;
                margin-bottom: 6px;
                font-weight: bold;
            }
            input {
                width: 100%;
                padding: 10px;
                box-sizing: border-box;
                border: 1px solid #ccc;
                border-radius: 8px;
            }
            button {
                margin-top: 18px;
                width: 100%;
                padding: 12px;
                border: none;
                border-radius: 999px;
                background: #1f2b4d;
                color: white;
                font-weight: bold;
                cursor: pointer;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Iniciar sessão</h1>
            <form method="post" action="/login">
                <label for="username">Utilizador</label>
                <input id="username" name="username" type="text" required>

                <label for="password">Palavra-passe</label>
                <input id="password" name="password" type="password" required>

                <button type="submit">Entrar</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.post("/login")
def login_submit(username: str = Form(...), password: str = Form(...)):
    if not credentials_are_valid(username, password):
        return HTMLResponse(
            """
            <html><body style="font-family: Arial; text-align:center; margin-top:60px;">
            <p>Credenciais inválidas.</p>
            <p><a href="/login">Voltar</a></p>
            </body></html>
            """,
            status_code=401,
        )

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_value(username),
        httponly=True,
        samesite="lax",
        secure=(os.getenv("APP_ENV") == "cloud"),
        max_age=60 * 60 * 12,
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response

@app.post("/drafts/from-text")
def create_draft_from_text(request: Request, payload: CreateDraftFromTextRequest):
    guard = require_login(request)
    if guard:
        return guard

    lines = [line.strip() for line in payload.text.splitlines() if line.strip()]

    items = build_draft_items_from_lines(
        lines=lines,
        worksheet_profile_name=payload.worksheet_profile_name,
        learner_profile=payload.learner_profile,
    )

    draft = create_empty_draft(
        title=payload.title,
        source_type="pasted",
        original_input_text=payload.text,
        worksheet_profile_name=payload.worksheet_profile_name,
        style_profile_name=payload.style_profile_name,
        learner_profile=payload.learner_profile,
        items=items,
    )

    save_draft(draft)
    return draft


@app.get("/drafts/{draft_id}")
def get_draft(request: Request, draft_id: str):
    guard = require_login(request)
    if guard:
        return guard

    return load_draft(draft_id)


@app.put("/drafts/{draft_id}")
def update_draft(request: Request, draft_id: str, payload: SaveDraftRequest):
    guard = require_login(request)
    if guard:
        return guard

    draft = load_draft(draft_id)

    draft.title = payload.title
    draft.worksheet_profile_name = payload.worksheet_profile_name
    draft.style_profile_name = payload.style_profile_name
    draft.learner_profile = payload.learner_profile
    draft.items = payload.items

    save_draft(draft)
    return draft


@app.post("/drafts/{draft_id}/generate")
def generate_from_draft(request: Request, draft_id: str):
    guard = require_login(request)
    if guard:
        return guard

    job_id, job_dir = create_job_dir()
    output_path = os.path.join(job_dir, "output.docx")
    status_path = os.path.join(job_dir, "status.json")

    update_status(status_path, status="processing", progress=0, message="A iniciar...")

    threading.Thread(
        target=process_draft_job,
        args=(draft_id, output_path, status_path),
        daemon=True
    ).start()

    return {"job_id": job_id}


@app.post("/drafts/{draft_id}/items/{item_id}/regenerate-question")
def regenerate_question_for_draft_item(
    request: Request,
    draft_id: str,
    item_id: str,
    payload: RegenerateQuestionRequest,
):
    guard = require_login(request)
    if guard:
        return guard

    draft = load_draft(draft_id)

    target_item = None
    for item in draft.items:
        if item.item_id == item_id:
            target_item = item
            break

    if target_item is None:
        return JSONResponse(status_code=404, content={"error": "Item not found"})

    # Use the family coming from the UI if provided
    exercise_family = payload.selected_exercise_family or target_item.selected_exercise_family or target_item.suggested_exercise_family

    # Persist the newly selected family into the draft
    target_item.selected_exercise_family = exercise_family

    if not exercise_family or exercise_family == "sem_pergunta":
        target_item.selected_question_pt = ""
        save_draft(draft)
        return target_item

    analysis = analyze_phrase(target_item.original)

    question_pt, answer_pt = build_question_from_family(
        analysis,
        exercise_family=exercise_family,
        learner_profile=draft.learner_profile,
    )

    target_item.selected_question_pt = question_pt
    save_draft(draft)

    return target_item


@app.get("/drafts")
def list_drafts(request: Request):
    guard = require_login(request)
    if guard:
        return guard

    return list_local_drafts()


from pathlib import Path
import json

@app.get("/question-families")
def get_question_families(request: Request):
    guard = require_login(request)
    if guard:
        return guard

    path = Path(__file__).resolve().parent / "question_families.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)