"""
Model-readiness reporting for GET /api/status.

The three pipelines are vendored third-party projects that each own their
own model singletons and load them lazily. Rather than reaching into them
eagerly (which would defeat the lazy loading and pull several GB into RAM
just to answer a status poll), this inspects whatever state already
exists and reports "not loaded" otherwise.

Every probe is wrapped: a status poll must never be the thing that breaks
the app, and an import here can fail legitimately (e.g. a build packaged
without the TTS weights).
"""

from __future__ import annotations


def _docs_translation_loaded() -> bool:
    try:
        from vendor.docs_baif.translator import translator

        return (
            translator.en_indic_model is not None
            or translator.indic_en_model is not None
        )
    except Exception:
        return False


def _audio_loaded() -> tuple[bool, bool, bool]:
    """(asr_loaded, translation_loaded, tts_loaded)"""
    try:
        from app.pipelines import audio

        pipeline = audio._pipeline
        if pipeline is None:
            return False, False, False

        return (
            pipeline.asr.model is not None,
            bool(pipeline.translator._models),
            pipeline._tts is not None,
        )
    except Exception:
        return False, False, False


def _video_loaded() -> tuple[bool, bool]:
    """(transcriber_loaded, translator_loaded)"""
    try:
        from vendor.video_baif.services import pipeline

        return (
            pipeline._transcriber is not None,
            pipeline._translator is not None
            and bool(pipeline._translator._models),
        )
    except Exception:
        return False, False


def model_status() -> list[dict]:
    audio_asr, audio_translation, audio_tts = _audio_loaded()
    video_asr, video_translation = _video_loaded()

    return [
        {
            "name": "IndicTrans2 (documents)",
            "task": "translation",
            "loaded": _docs_translation_loaded(),
            "sizeMb": None,
        },
        {
            "name": "faster-whisper medium (audio)",
            "task": "asr",
            "loaded": audio_asr,
            "sizeMb": None,
        },
        {
            "name": "IndicTrans2 (audio)",
            "task": "translation",
            "loaded": audio_translation,
            "sizeMb": None,
        },
        {
            "name": "Indic Parler-TTS (dubbing)",
            "task": "tts",
            "loaded": audio_tts,
            "sizeMb": None,
        },
        {
            "name": "faster-whisper medium (video)",
            "task": "asr",
            "loaded": video_asr,
            "sizeMb": None,
        },
        {
            "name": "NLLB-200 distilled 600M (video)",
            "task": "translation",
            "loaded": video_translation,
            "sizeMb": None,
        },
    ]
