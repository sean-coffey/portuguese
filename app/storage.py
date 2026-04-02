# app/storage.py
from app.config import APP_ENV

def use_s3() -> bool:
    return APP_ENV == "cloud"