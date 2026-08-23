from __future__ import annotations

import torch

from app import config
from app.core.asr import asr
from app.core.translation import translator


def gpu_available() -> bool:
    """
    Whether this build of torch can see a usable CUDA GPU. Deliberately
    defensive: a CPU-only build (the default for packaged installs) never
    has CUDA support compiled in, and on a GPU build, driver detection can
    still fail in unexpected ways on a machine we don't control -- either
    way this should report False, never raise.
    """

    try:
        return torch.cuda.is_available()
    except Exception:
        return False


def set_device(device: str) -> None:
    """
    Switch ASR/translation to `device` ("cpu" or "cuda") app-wide. TTS is
    deliberately left out -- see below.

    This is an app-wide setting, not per-job: each model wrapper drops its
    already-loaded weights so the next call reloads them on the new device,
    rather than the app holding two loaded copies of multi-GB models at
    once.

    TTS never follows this toggle and always runs on CPU, regardless of
    `device`: ASR (faster-whisper) is built on ctranslate2, which is
    imported unconditionally at startup (app.core.asr imports faster_whisper
    which imports ctranslate2) and, at least on Windows, permanently breaks
    torch's own CUDA/cuDNN symbol resolution for the rest of the process
    once it's loaded -- confirmed by reproduction: `import ctranslate2`
    followed by *any* CUDA op in torch (regardless of ctranslate2 ever
    actually running a model) aborts the whole interpreter with "Could not
    load symbol cudnnGetLibConfig. Error code 127" and no catchable Python
    exception, while the identical torch CUDA op works fine without
    ctranslate2 imported first, and CPU-only torch ops work fine either way.
    Since ctranslate2 is always in-process here, torch (used by TTS/Parler)
    can never safely touch CUDA in this app -- there is no per-job or
    per-toggle way around it short of running TTS out-of-process.
    """

    asr.set_device(device)
    translator.set_device(device)

    config.ASR_DEVICE = device
    config.TRANSLATION_DEVICE = device
