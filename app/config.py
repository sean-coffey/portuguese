import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
IMAGE_DIR = os.path.join(BASE_DIR, "images")
DATA_DIR = os.path.join(BASE_DIR, "data")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

REFERENCE_ASSETS_DIR = os.path.join(BASE_DIR, "reference_assets")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
STYLE_GUIDE_PATH = os.path.join(PROMPTS_DIR, "style_guide.txt")

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REFERENCE_ASSETS_DIR, exist_ok=True)
os.makedirs(PROMPTS_DIR, exist_ok=True)