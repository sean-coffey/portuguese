# app/api.py

import os
import uuid
import shutil
import json

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse

from app.pipeline import process_document
from app.config import BASE_DIR

app = FastAPI()

JOBS_DIR = os.path.join(BASE_DIR, "data", "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)


def create_job_dir():
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    return job_id, job_dir


# ---------------------------
# Upload + process
# ---------------------------
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename.endswith(".docx"):
        return JSONResponse(
            status_code=400,
            content={"error": "Only .docx files are supported"}
        )

    job_id, job_dir = create_job_dir()

    input_path = os.path.join(job_dir, "input.docx")
    output_path = os.path.join(job_dir, "output.docx")

    # Save uploaded file
    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    original_name = file.filename

    with open(os.path.join(job_dir, "meta.json"), "w") as f:
        json.dump({"original_filename": original_name}, f)

    try:
        # 🔥 Use your existing pipeline (no changes needed)
        process_document(
            input_path=input_path,
            output_filename=os.path.basename(output_path)
        )

        return {
            "job_id": job_id,
            "status": "completed",
            "download_url": f"/download/{job_id}"
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "job_id": job_id,
                "status": "failed",
                "error": str(e)
            }
        )


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

