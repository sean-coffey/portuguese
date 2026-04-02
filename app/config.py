import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

APP_ENV = os.getenv("APP_ENV", "local")

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
IMAGE_DIR = BASE_DIR / "images"
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"

REFERENCE_ASSETS_DIR = BASE_DIR / "reference_assets"
PROMPTS_DIR = BASE_DIR / "prompts"
STYLE_GUIDE_PATH = PROMPTS_DIR / "style_guide.txt"

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")

for folder in [INPUT_DIR, OUTPUT_DIR, IMAGE_DIR, DATA_DIR, TEMPLATES_DIR, REFERENCE_ASSETS_DIR, PROMPTS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)