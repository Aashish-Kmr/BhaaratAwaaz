from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

UPLOAD_DIR = BASE_DIR / "uploads"
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "outputs"
MODELS_DIR = BASE_DIR / "models"

for directory in (
    UPLOAD_DIR,
    TEMP_DIR,
    OUTPUT_DIR,
    MODELS_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)


# -----------------------------
# ASR
# -----------------------------

WHISPER_MODEL = "base"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"


# -----------------------------
# Languages
# -----------------------------

LANGUAGE_CODES = {
    "marathi": "mr",
    "hindi": "hi",
    "english": "en",
}

INDIC_LANG_CODES = {
    "mr": "mar_Deva",
    "hi": "hin_Deva",
    "en": "eng_Latn",
}


# -----------------------------
# Translation model
# -----------------------------

INDICTRANS_MODEL = (
    "ai4bharat/indictrans2-indic-indic-dist-320M"
)