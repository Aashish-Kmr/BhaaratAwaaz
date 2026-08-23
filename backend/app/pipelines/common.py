from __future__ import annotations

from typing import Callable

from app import config
from app.core.translation import translator
from app.core.tts import tts
from app.jobs.models import Job, Segment
from app.jobs.store import JobStore


def should_stop_fn(store: JobStore, job_id: str) -> Callable[[], bool]:
    def check() -> bool:
        job = store.try_get(job_id)
        return job is None or job.cancel_requested

    return check


def maybe_dub(
    job: Job,
    store: JobStore,
    segments: list[Segment],
    should_stop: Callable[[], bool],
) -> None:
    """
    Synthesize the dubbed track if the job opted in. Shared by the audio and
    video pipelines, which otherwise do the same thing: join the translated
    segment text and synthesize one WAV.

    Runs inline as the last pipeline stage — on the worker's single
    processing thread, same as every other stage — so a job that asked for
    dubbing is only ever reported "done" once the dubbed track actually
    exists, and a synthesis failure fails the job (with a real error)
    instead of silently finishing without the track the user asked for.
    """

    if not job.include_dubbing:
        return

    if should_stop():
        raise InterruptedError("cancelled")

    store.update(job.id, status="dubbing", stage="Dubbing audio", progress=0.97)

    translated_text = " ".join(s.target for s in segments if s.target).strip()
    if not translated_text:
        return

    tts.synthesize(translated_text, job.target_lang, job.dubbed_audio_file)
    store.update(job.id, dubbed_audio_ready=True)


def translate_segments(
    job_id: str,
    store: JobStore,
    raw_segments: list[dict],
    source_lang: str,
    target_lang: str,
    should_stop: Callable[[], bool],
    progress_start: float,
    progress_span: float,
) -> list[Segment]:
    """
    Translate ASR segments in batches (see Translator.translate_batch) rather
    than one at a time -- far fewer model.generate() calls for a transcript
    with many short segments. Progress is still reported after each batch so
    the UI doesn't look frozen on long transcripts.
    """

    total = max(1, len(raw_segments))
    segments: list[Segment] = []
    batch_size = config.TRANSLATION_BATCH_SIZE

    for chunk_start in range(0, len(raw_segments), batch_size):
        if should_stop():
            raise InterruptedError("cancelled")

        chunk = raw_segments[chunk_start : chunk_start + batch_size]
        texts = [raw["text"] for raw in chunk]

        translated_texts = translator.translate_batch(texts, source_lang, target_lang)

        for raw, target_text in zip(chunk, translated_texts):
            segments.append(
                Segment(
                    id=f"{job_id}_s{raw['id']}",
                    start=raw["start"],
                    end=raw["end"],
                    source=raw["text"],
                    target=target_text,
                    confidence=raw.get("confidence"),
                )
            )

        done = chunk_start + len(chunk)
        store.update(job_id, progress=progress_start + done / total * progress_span)

    return segments
