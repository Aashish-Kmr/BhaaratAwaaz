"""
Vendored from BAIF-main/config.py.

Only the *paths* are bridged to the host app's data directory so this
pipeline reuses the models/fonts already downloaded under backend/data
instead of expecting its own BAIF-main/models/ tree (which was never
populated). LANGUAGE_CODES and SUPPORTED_EXTENSIONS are unchanged.

Model directory names differ from the original: this project asked for
"indictrans2-en-indic" / "indictrans2-indic-en", while what is actually
downloaded (and what the audio pipeline also uses) are the distilled
checkpoints "indictrans2-en-indic-dist-200M" / "-indic-en-dist-200M".
Pointing at the shared copies avoids a second multi-GB download of the
same weights.
"""

from pathlib import Path

from app import config as _host


BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# MODEL PATHS  (shared with the audio pipeline)
# ============================================================

# English -> Hindi / Marathi
EN_INDIC_MODEL_PATH = (
    _host.TRANSLATION_MODEL_DIR / "indictrans2-en-indic-dist-200M"
)

# Hindi / Marathi -> English
INDIC_EN_MODEL_PATH = (
    _host.TRANSLATION_MODEL_DIR / "indictrans2-indic-en-dist-200M"
)


# ============================================================
# FILE DIRECTORIES
# ============================================================
#
# The originals were BASE_DIR/uploads and BASE_DIR/translated, created at
# import time. In a packaged build BASE_DIR lives inside Program Files and
# is not writable, so these follow the host's per-user job directory
# instead. The document adapter passes explicit paths anyway; these remain
# only so the module's public surface is unchanged.

UPLOAD_DIR = _host.JOBS_DIR / "_docs_uploads"
OUTPUT_DIR = _host.JOBS_DIR / "_docs_translated"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


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
