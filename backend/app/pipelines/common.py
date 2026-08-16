from __future__ import annotations

from typing import Callable

from app import config
from app.core.translation import translator
from app.jobs.models import Segment
from app.jobs.store import JobStore


def should_stop_fn(store: JobStore, job_id: str) -> Callable[[], bool]:
    def check() -> bool:
        job = store.try_get(job_id)
        return job is None or job.cancel_requested

    return check


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
