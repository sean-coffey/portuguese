# app/api.py

import os
import uuid
import shutil
import json
import threading

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
from app.pipeline import process_document
from app.jobs.utils import update_status
from app.config import BASE_DIR
from app.storage import use_s3, upload_file_to_s3, generate_download_url

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

JOBS_DIR = os.path.join(BASE_DIR, "data", "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)


def create_job_dir():
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    return job_id, job_dir


def process_job(input_path, output_path, status_path):
    try:
        update_status(status_path, status="processing", progress=0, message="A iniciar...")

        local_output_path = process_document(
            input_path=input_path,
            output_filename=os.path.basename(output_path),
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
async def upload(request: Request, file: UploadFile = File(...)):
    guard = require_login(request)
    if guard:
        return guard

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
        args=(input_path, output_path, status_path),
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