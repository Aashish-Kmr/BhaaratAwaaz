from __future__ import annotations

import os
import sys
from pathlib import Path


def _app_root() -> Path:
    """
    Root directory the app is running from.

    When frozen by PyInstaller, `sys.executable` is the bundled binary and
    everything the app ships (frontend/dist, fonts) lives next to it.
    Otherwise it's the `backend/` package root (two parents up from this file).
    """

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


APP_ROOT = _app_root()
REPO_ROOT = APP_ROOT.parent if not getattr(sys, "frozen", False) else APP_ROOT

# ----------------------------------------------------------------------
# Data / model / static directories
# ----------------------------------------------------------------------

DATA_DIR = Path(os.getenv("BAIF_DATA_DIR", APP_ROOT / "data"))
JOBS_DIR = DATA_DIR / "jobs"
MODELS_DIR = Path(os.getenv("BAIF_MODELS_DIR", DATA_DIR / "models"))
TRANSLATION_MODEL_DIR = MODELS_DIR / "translation"

# faster-whisper and Parler-TTS pull their weights through huggingface_hub's
# own cache, which defaults to ~/.cache/huggingface -- outside the project
# and different on every machine, so it can't be bundled predictably.
# Redirecting HF_HOME here puts everything under one folder we control and
# can ship with the app (see pyinstaller.spec) instead of re-downloading on
# every machine. Must happen before anything imports torch/transformers/
# huggingface_hub; config.py is the first thing every other module here
# imports, so this is early enough as long as nothing above this line does.
HF_CACHE_DIR = Path(os.getenv("HF_HOME", DATA_DIR / "hf_cache"))
os.environ.setdefault("HF_HOME", str(HF_CACHE_DIR))

FRONTEND_DIST_DIR = Path(os.getenv("BAIF_FRONTEND_DIST", REPO_ROOT / "frontend" / "dist"))
FONT_DIR = Path(os.getenv("BAIF_FONT_DIR", REPO_ROOT / "fonts"))
DEVANAGARI_FONT_PATH = FONT_DIR / "NotoSansDevanagari-Regular.ttf"

for directory in (DATA_DIR, JOBS_DIR, MODELS_DIR, TRANSLATION_MODEL_DIR, HF_CACHE_DIR):
    directory.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------
# Languages
# ----------------------------------------------------------------------

SUPPORTED_LANGUAGES = {"en", "hi", "mr"}

FLORES_CODES = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "mr": "mar_Deva",
}

LANGUAGE_LABELS = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
}

# ----------------------------------------------------------------------
# File kinds
# ----------------------------------------------------------------------

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".csv"}

ALL_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | DOCUMENT_EXTENSIONS

MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB


def kind_of(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()

    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in DOCUMENT_EXTENSIONS:
        return "document"
    return None


# ----------------------------------------------------------------------
# Model settings (overridable via env for packaging / low-resource boxes)
# ----------------------------------------------------------------------

ASR_MODEL = os.getenv("BAIF_ASR_MODEL", "medium")
ASR_DEVICE = os.getenv("BAIF_ASR_DEVICE", "cpu")
ASR_COMPUTE_TYPE = os.getenv("BAIF_ASR_COMPUTE_TYPE", "int8")
ASR_BEAM_SIZE = int(os.getenv("BAIF_ASR_BEAM_SIZE", "5"))

TRANSLATION_DEVICE = os.getenv("BAIF_TRANSLATION_DEVICE", "cpu")
TTS_DEVICE = os.getenv("BAIF_TTS_DEVICE") or None

VAD_ENABLED = True
VAD_MIN_SILENCE_MS = 500

MEDIA_HOST = os.getenv("BAIF_HOST", "127.0.0.1")
MEDIA_PORT = int(os.getenv("BAIF_PORT", "8000"))
