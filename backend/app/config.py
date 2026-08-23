from __future__ import annotations

import os
import sys
from pathlib import Path


def _app_root() -> Path:
    """
    Root directory bundled resources (frontend/dist, fonts, the pre-
    downloaded model weights) ship from.

    When frozen by PyInstaller in --onedir mode, everything except the
    launcher .exe itself lives under a `_internal/` subfolder next to it
    (PyInstaller 6.0's default "contents directory" layout) -- NOT directly
    next to sys.executable. sys._MEIPASS is PyInstaller's own documented way
    to find that folder regardless of layout details, and for --onedir
    specifically it's a stable, permanent directory (not re-extracted per
    launch the way --onefile's temp _MEIPASS is), so it's safe to treat as a
    normal read location. Otherwise it's the `backend/` package root (two
    parents up from this file).
    """

    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))

    return Path(__file__).resolve().parent.parent


APP_ROOT = _app_root()
REPO_ROOT = APP_ROOT.parent if not getattr(sys, "frozen", False) else APP_ROOT

# ----------------------------------------------------------------------
# Data / model / static directories
# ----------------------------------------------------------------------

# Model weights baked in at build time -- read-only in practice, and inside
# the app's install folder (e.g. under Program Files), so keep it there.
DATA_DIR = Path(os.getenv("BAIF_DATA_DIR", APP_ROOT / "data"))

# Job uploads/outputs are written continuously at runtime, unlike the model
# weights above -- a frozen build is typically installed under Program
# Files, where a standard (non-admin) user cannot write, so default this to
# a normal per-user data folder instead of nesting it under DATA_DIR/APP_ROOT
# like the dev layout does. BAIF_DATA_DIR / BAIF_JOBS_DIR both still override.
if getattr(sys, "frozen", False) and not os.getenv("BAIF_DATA_DIR"):
    JOBS_DIR = Path(
        os.getenv("BAIF_JOBS_DIR", Path(os.environ["LOCALAPPDATA"]) / "BAIF Bhasha" / "jobs")
    )
else:
    JOBS_DIR = Path(os.getenv("BAIF_JOBS_DIR", DATA_DIR / "jobs"))

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

# huggingface_hub tries to write an updated cache ref pointer on every
# from_pretrained()/snapshot_download() call, even when the model is already
# fully cached and nothing actually changed -- confirmed by loading
# faster-whisper with this unset and watching it touch
# hf_cache/hub/.../refs/main every time. In a packaged build installed under
# Program Files, a standard (non-admin) user can't write there, so that
# turns into a PermissionError the moment a job actually runs a model,
# despite the app starting up fine. This app is designed to run fully
# offline once scripts/download_models.py has fetched everything anyway
# (see PACKAGING.md), so forcing offline mode here avoids the write
# entirely instead of trying to make the install dir writable.
# download_models.py explicitly re-enables this before it downloads
# anything -- that's the one script that needs network access.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

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
# 0 = let ctranslate2 pick (its own default was as good as or better than
# forcing all cores when benchmarked on Apple Silicon -- more threads isn't
# automatically faster, especially on P+E core CPUs). Worth experimenting
# with on whatever machine actually runs the demo.
ASR_CPU_THREADS = int(os.getenv("BAIF_ASR_CPU_THREADS", "0"))

TRANSLATION_DEVICE = os.getenv("BAIF_TRANSLATION_DEVICE", "cpu")
# How many segments/paragraphs go into one model.generate() call. Higher is
# faster (fewer calls, better CPU utilization) but uses more memory per call.
TRANSLATION_BATCH_SIZE = int(os.getenv("BAIF_TRANSLATION_BATCH_SIZE", "8"))
# Beam search width for translation. Lower is faster with a small quality
# tradeoff -- try 1 (greedy) or 3 if translation is the bottleneck.
TRANSLATION_NUM_BEAMS = int(os.getenv("BAIF_TRANSLATION_NUM_BEAMS", "5"))
# unset = leave torch's own default thread count alone (same reasoning as
# ASR_CPU_THREADS above -- benchmarked no better, sometimes worse, on this
# machine when forced to all cores).
TORCH_NUM_THREADS = int(os.environ["BAIF_TORCH_THREADS"]) if os.getenv("BAIF_TORCH_THREADS") else None
TTS_DEVICE = os.getenv("BAIF_TTS_DEVICE", "cpu")

VAD_ENABLED = True
VAD_MIN_SILENCE_MS = 500

MEDIA_HOST = os.getenv("BAIF_HOST", "127.0.0.1")
MEDIA_PORT = int(os.getenv("BAIF_PORT", "8000"))
