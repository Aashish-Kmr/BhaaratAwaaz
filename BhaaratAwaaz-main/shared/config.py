from __future__ import annotations

import os
from pathlib import Path


# Project root: BhaaratAwaaz/
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Config:
    # --------------------------------------------------
    # Directories
    # --------------------------------------------------

    DATA_DIR = PROJECT_ROOT / "data"
    INPUT_DIR = DATA_DIR / "input"
    OUTPUT_DIR = DATA_DIR / "output"
    TEMP_DIR = DATA_DIR / "temp"

    MODELS_DIR = PROJECT_ROOT / "models" / "audio"

    # --------------------------------------------------
    # ASR
    # --------------------------------------------------

    ASR_MODEL = os.getenv("BAHAARTAWAAZ_ASR_MODEL", "medium")
    ASR_DEVICE = os.getenv("BAHAARTAWAAZ_ASR_DEVICE", "cpu")
    ASR_COMPUTE_TYPE = os.getenv(
        "BAHAARTAWAAZ_ASR_COMPUTE_TYPE",
        "int8",
    )

    ASR_BEAM_SIZE = 5

    # VAD
    VAD_ENABLED = True
    VAD_MIN_SILENCE_MS = 500

    # --------------------------------------------------
    # Translation
    # --------------------------------------------------

    TRANSLATION_MODEL_DIR = MODELS_DIR

    TRANSLATION_DEVICE = os.getenv(
        "BAHAARTAWAAZ_TRANSLATION_DEVICE",
        "cpu",
    )

    # --------------------------------------------------
    # Audio
    # --------------------------------------------------

    SAMPLE_RATE = 16000
    CHANNELS = 1
    AUDIO_FORMAT = "wav"

    TTS_DEVICE = os.getenv(
        "BAHAARTAWAAZ_TTS_DEVICE", None
    )

    @classmethod
    def create_directories(cls):
        """Create required project directories."""

        directories = [
            cls.INPUT_DIR,
            cls.OUTPUT_DIR,
            cls.TEMP_DIR,
            cls.MODELS_DIR,
        ]

        for directory in directories:
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )
    