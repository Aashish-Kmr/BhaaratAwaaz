"""
Vendored from BAIF-Video-main/.../app/config.py.

Only the directories are bridged to the host app's data directory (the
originals were created at import time inside the install folder, which is
read-only in a packaged build). Model choice, language tables and
device settings are unchanged -- they were already CPU-only upstream.
"""

from pathlib import Path

from app import config as _host


BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = _host.JOBS_DIR / "_video" / "uploads"
TEMP_DIR = _host.JOBS_DIR / "_video" / "temp"
OUTPUT_DIR = _host.JOBS_DIR / "_video" / "outputs"
MODELS_DIR = _host.MODELS_DIR

for directory in (
    UPLOAD_DIR,
    TEMP_DIR,
    OUTPUT_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)


# -----------------------------
# ASR
# -----------------------------
#
# Note: services/transcriber.py sets its own size (Transcriber.MODEL_SIZE,
# now "medium") and ignores these; they are kept so the module's public
# surface is unchanged.

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
#
# Unused by the active translator (services/translator.py uses NLLB-200);
# kept for parity with upstream.

INDICTRANS_MODEL = (
    "ai4bharat/indictrans2-indic-indic-dist-320M"
)
