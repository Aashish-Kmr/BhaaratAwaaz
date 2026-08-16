from __future__ import annotations

import threading

from app.core import audio_preprocess
from app.core.asr import asr
from app.core.tts import tts
from app.jobs.models import Job, Segment
from app.jobs.store import JobStore
from app.pipelines.common import should_stop_fn, translate_segments


def run(job: Job, store: JobStore) -> None:
    should_stop = should_stop_fn(store, job.id)

    store.update(job.id, status="extracting", stage="Extracting audio", progress=0.05)

    normalized = audio_preprocess.preprocess_audio(
        input_path=job.input_file,
        output_directory=job.job_path / "tmp",
    )
    store.update(job.id, duration_sec=normalized.duration_seconds)

    if should_stop():
        raise InterruptedError("cancelled")

    store.update(job.id, status="transcribing", stage="Transcribing", progress=0.15)

    def on_asr_progress(fraction: float) -> None:
        store.update(job.id, progress=0.15 + fraction * 0.4)

    asr_result = asr.transcribe(
        normalized.output_path,
        language=job.source_lang,
        duration_hint=normalized.duration_seconds,
        on_progress=on_asr_progress,
        should_stop=should_stop,
    )

    if should_stop():
        raise InterruptedError("cancelled")

    store.update(job.id, status="translating", stage="Translating", progress=0.55)

    segments = translate_segments(
        job.id,
        store,
        asr_result["segments"],
        job.source_lang,
        job.target_lang,
        should_stop,
        progress_start=0.55,
        progress_span=0.4,
    )

    store.save_segments(job.id, segments)

    # Dubbed-audio (TTS) is a best-effort bonus artifact. It runs on its own
    # thread so it never blocks the job from being marked "done" or blocks
    # the single worker from picking up the next queued job.
    threading.Thread(
        target=_dub_in_background, args=(job, store, segments), daemon=True
    ).start()


def _dub_in_background(job: Job, store: JobStore, segments: list[Segment]) -> None:
    try:
        translated_text = " ".join(s.target for s in segments if s.target).strip()
        if not translated_text:
            return
        tts.synthesize(translated_text, job.target_lang, job.dubbed_audio_file)
        if store.try_get(job.id) is not None:
            store.update(job.id, dubbed_audio_ready=True)
    except Exception:
        pass
