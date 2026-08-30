"""
Audio job adapter.

Thin bridge between the host job queue and the vendored BhaaratAwaaz-main
audio pipeline (backend/vendor/audio_ba). Preprocessing, ASR, translation
and TTS all live there; this module only maps a Job onto
AudioPipeline.process() and translates its result back into the host's
Segment shape.
"""

from __future__ import annotations

import shutil
import threading
from pathlib import Path

from app.jobs.models import Job, Segment
from app.jobs.store import JobStore
from app.pipelines.common import should_stop_fn

from vendor.audio_ba.modules.audio.pipeline import AudioPipeline

# AudioPipeline's constructor eagerly loads the faster-whisper model, so
# it is built once on first use and reused for the process lifetime
# rather than per job. The worker runs a single job at a time, so one
# shared instance is enough; the lock only guards construction.
_pipeline: AudioPipeline | None = None
_pipeline_lock = threading.Lock()


def _get_pipeline() -> AudioPipeline:
    global _pipeline

    with _pipeline_lock:
        if _pipeline is None:
            _pipeline = AudioPipeline()
        return _pipeline


def run(job: Job, store: JobStore) -> None:
    should_stop = should_stop_fn(store, job.id)

    store.update(job.id, status="extracting", stage="Extracting audio", progress=0.05)

    def on_progress(fraction: float) -> None:
        # Map the vendored pipeline's stage boundaries onto the host's
        # status vocabulary so the queue shows a meaningful stage label.
        if fraction < 0.15:
            status, stage = "extracting", "Extracting audio"
        elif fraction < 0.55:
            status, stage = "transcribing", "Transcribing"
        elif fraction < 0.95:
            status, stage = "translating", "Translating"
        else:
            status, stage = (
                ("dubbing", "Dubbing audio")
                if job.include_dubbing
                else ("translating", "Translating")
            )

        store.update(job.id, status=status, stage=stage, progress=fraction)

    result = _get_pipeline().process(
        input_audio=job.input_file,
        target_language=job.target_lang,
        source_language=job.source_lang,
        include_dubbing=job.include_dubbing,
        on_progress=on_progress,
        should_stop=should_stop,
        temp_dir=job.job_path / "tmp",
        output_dir=job.job_path,
    )

    duration = result.get("normalized_audio", {}).get("duration_seconds")
    if duration:
        store.update(job.id, duration_sec=duration)

    segments = [
        Segment(
            id=f"{job.id}_s{raw['id']}",
            start=raw["start"],
            end=raw["end"],
            source=raw["source_text"],
            target=raw["translated_text"],
        )
        for raw in result["segments"]
    ]

    store.save_segments(job.id, segments)

    # The vendored pipeline names its output <stem>_<lang>.wav; the host
    # serves the dubbed track from a fixed path, so point one at the other.
    output_audio = result.get("output_audio")
    if output_audio:
        dubbed = job.dubbed_audio_file
        if Path(output_audio) != dubbed:
            shutil.copyfile(output_audio, dubbed)
        store.update(job.id, dubbed_audio_ready=True)
