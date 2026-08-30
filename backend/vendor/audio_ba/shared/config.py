"""
Vendored from BhaaratAwaaz-main/shared/config.py.

Directories and the model root are bridged to the host app's data
directory (models are shared with the document pipeline rather than
duplicated under a private models/audio/ tree, which was never
populated). Devices are pinned to CPU: this build is CPU-only, and these
were already the upstream defaults.
"""

from __future__ import annotations

import os
from pathlib import Path

from app import config as _host


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Config:
    # --------------------------------------------------
    # Directories
    # --------------------------------------------------
    #
    # Upstream used PROJECT_ROOT/data/{input,output,temp}. Those sit
    # inside the install directory, which is read-only in a packaged
    # build, so they follow the host's per-user job directory instead.
    # AudioPipeline.process() also accepts explicit temp/output
    # directories, which is what the job adapter actually passes.

    DATA_DIR = _host.JOBS_DIR / "_audio"
    INPUT_DIR = DATA_DIR / "input"
    OUTPUT_DIR = DATA_DIR / "output"
    TEMP_DIR = DATA_DIR / "temp"

    # Shared with the document pipeline -- same IndicTrans2 checkpoints.
    MODELS_DIR = _host.TRANSLATION_MODEL_DIR

    # --------------------------------------------------
    # ASR
    # --------------------------------------------------

    ASR_MODEL = os.getenv("BAHAARTAWAAZ_ASR_MODEL", "medium")
    ASR_DEVICE = "cpu"
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

    TRANSLATION_DEVICE = "cpu"

    # --------------------------------------------------
    # Audio
    # --------------------------------------------------

    SAMPLE_RATE = 16000
    CHANNELS = 1
    AUDIO_FORMAT = "wav"

    # Upstream defaulted to None, which made TTS auto-select CUDA when a
    # GPU was visible. Pinned to CPU here: this build is CPU-only, and
    # ctranslate2 (loaded by the ASR stage in this same process) breaks
    # torch's CUDA/cuDNN symbol resolution on Windows anyway.
    TTS_DEVICE = "cpu"

    @classmethod
    def create_directories(cls):
        """Create required project directories."""

        directories = [
            cls.INPUT_DIR,
            cls.OUTPUT_DIR,
            cls.TEMP_DIR,
        ]

        for directory in directories:
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )
