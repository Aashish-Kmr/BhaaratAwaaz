from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# MODEL PATHS
# ============================================================

# English -> Hindi / Marathi
EN_INDIC_MODEL_PATH = (
    BASE_DIR / "models" / "indictrans2-en-indic"
)

# Hindi / Marathi -> English
INDIC_EN_MODEL_PATH = (
    BASE_DIR / "models" / "indictrans2-indic-en"
)


# ============================================================
# FILE DIRECTORIES
# ============================================================

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "translated"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# ============================================================
# LANGUAGE CODES
# ============================================================

LANGUAGE_CODES = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "mr": "mar_Deva",
}


SUPPORTED_EXTENSIONS = {
    ".docx",
    ".pptx",
    ".xlsx",
    ".csv",
    ".pdf",
}