from faster_whisper import WhisperModel

_MODEL = None


def get_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = WhisperModel(
            "base",
            device="cpu",
            compute_type="int8",
        )
    return _MODEL


def transcribe_audio(audio_path: str, source_language: str | None = None) -> list[dict]:
    model = get_model()

    segments, info = model.transcribe(
        audio_path,
        language=source_language,
        vad_filter=True,
        beam_size=1,
    )

    results = []
    for seg in segments:
        results.append(
            {
                "start": float(seg.start),
                "end": float(seg.end),
                "source_text": seg.text.strip(),
            }
        )

    return results