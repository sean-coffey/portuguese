# app/storage.py
import os
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.config import APP_ENV

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")

def get_s3_client():
    return boto3.client("s3", region_name=AWS_REGION)


def use_s3() -> bool:
    return APP_ENV == "cloud" and bool(S3_BUCKET_NAME)


def upload_file_to_s3(local_path: str, s3_key: str) -> str:
    if not S3_BUCKET_NAME:
        raise RuntimeError("S3_BUCKET_NAME is not set")
    s3 = get_s3_client()
    s3.upload_file(local_path, S3_BUCKET_NAME, s3_key)
    return s3_key


def generate_download_url(s3_key: str, expires_in: int = 3600) -> str:
    if not S3_BUCKET_NAME:
        raise RuntimeError("S3_BUCKET_NAME is not set")
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=expires_in,
    )