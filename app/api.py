# app/api.py

import os
import uuid
import shutil
import json

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


from app.pipeline import process_document
from app.jobs.utils import update_status
from app.config import BASE_DIR

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
        update_status(status_path, status="processing", progress=0, message="Parsing document")

        process_document(
            input_path=input_path,
            output_filename=os.path.basename(output_path),
            status_path=status_path   # 👈 NEW
        )

        update_status(status_path, status="completed", progress=100, message="Done")

    except Exception as e:
        update_status(status_path, status="failed", message=str(e))

@app.get("/")
def serve_ui():
    return FileResponse("app/static/index.html")


# ---------------------------
# Upload + process
# ---------------------------
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    job_id, job_dir = create_job_dir()

    input_path = os.path.join(job_dir, "input.docx")
    output_path = os.path.join(job_dir, "output.docx")

    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # create initial status file
    status_path = os.path.join(job_dir, "status.json")
    with open(status_path, "w") as f:
        json.dump({"status": "processing", "progress": 0}, f)

    # run in background (simple version)
    import threading
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
def download(job_id: str):
    job_dir = os.path.join(JOBS_DIR, job_id)
    output_path = os.path.join(job_dir, "output.docx")

    if not os.path.exists(output_path):
        return JSONResponse(
            status_code=404,
            content={"error": "File not found"}
        )

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="worksheet.docx"
    )


@app.get("/status/{job_id}")
def get_status(job_id: str):
    status_path = os.path.join(JOBS_DIR, job_id, "status.json")

    if not os.path.exists(status_path):
        return {"status": "not_found"}

    with open(status_path) as f:
        return json.load(f)
