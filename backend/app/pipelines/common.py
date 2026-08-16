from __future__ import annotations

from typing import Callable

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
    """Translate ASR segments one at a time, reporting incremental progress."""

    total = max(1, len(raw_segments))
    segments: list[Segment] = []

    for index, raw in enumerate(raw_segments):
        if should_stop():
            raise InterruptedError("cancelled")

        target_text = translator.translate(raw["text"], source_lang, target_lang)

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

        store.update(job_id, progress=progress_start + (index + 1) / total * progress_span)

    return segments
