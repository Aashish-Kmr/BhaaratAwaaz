from __future__ import annotations

import os
from pathlib import Path


# ============================================================
# Project Root
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Config:

    # ========================================================
    # Directories
    # ========================================================

    DATA_DIR = PROJECT_ROOT / "data"

    INPUT_DIR = DATA_DIR / "input"
    OUTPUT_DIR = DATA_DIR / "output"
    TEMP_DIR = DATA_DIR / "temp"

    MODELS_DIR = PROJECT_ROOT / "models" / "audio"

    # ========================================================
    # ASR
    # ========================================================

    ASR_MODEL = os.getenv(
        "BAHAARTAWAAZ_ASR_MODEL",
        "medium",
    )

    ASR_DEVICE = os.getenv(
        "BAHAARTAWAAZ_ASR_DEVICE",
        "cpu",
    )

    ASR_COMPUTE_TYPE = os.getenv(
        "BAHAARTAWAAZ_ASR_COMPUTE_TYPE",
        "int8",
    )

    # Faster-Whisper beam size.
    #
    # 5 = better quality but slower
    # 3 = good balance
    # 1 = fastest
    ASR_BEAM_SIZE = int(
        os.getenv(
            "BAHAARTAWAAZ_ASR_BEAM_SIZE",
            "3",
        )
    )

    # ========================================================
    # VAD
    # ========================================================

    VAD_ENABLED = True

    VAD_MIN_SILENCE_MS = 500

    # ========================================================
    # Translation
    # ========================================================

    TRANSLATION_MODEL_DIR = MODELS_DIR

    TRANSLATION_DEVICE = os.getenv(
        "BAHAARTAWAAZ_TRANSLATION_DEVICE",
        "cpu",
    )

    # Number of ASR segments translated together.
    #
    # Larger batch:
    #     faster throughput
    #     more RAM
    #
    # Smaller batch:
    #     lower RAM
    #     potentially slower
    #
    TRANSLATION_BATCH_SIZE = int(
        os.getenv(
            "BAHAARTAWAAZ_TRANSLATION_BATCH_SIZE",
            "16",
        )
    )

    # Beam search.
    #
    # 5 = highest quality / slow
    # 3 = balanced
    # 2 = fast
    # 1 = fastest
    TRANSLATION_BEAM_SIZE = int(
        os.getenv(
            "BAHAARTAWAAZ_TRANSLATION_BEAM_SIZE",
            "2",
        )
    )

    # Maximum generated tokens.
    #
    # Keep this reasonably small because ASR segments
    # are normally short.
    TRANSLATION_MAX_LENGTH = int(
        os.getenv(
            "BAHAARTAWAAZ_TRANSLATION_MAX_LENGTH",
            "128",
        )
    )

    # Minimum generated tokens.
    TRANSLATION_MIN_LENGTH = 0

    # Use sampling only if explicitly enabled.
    # False gives deterministic translation.
    TRANSLATION_DO_SAMPLE = False

    # ========================================================
    # Audio
    # ========================================================

    SAMPLE_RATE = 16000

    CHANNELS = 1

    AUDIO_FORMAT = "wav"

    # ========================================================
    # TTS
    # ========================================================

    TTS_DEVICE = os.getenv(
        "BAHAARTAWAAZ_TTS_DEVICE",
        None,
    )

    # ========================================================
    # Directory creation
    # ========================================================

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
