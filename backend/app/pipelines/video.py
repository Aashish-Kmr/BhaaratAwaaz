from __future__ import annotations

import subprocess
from pathlib import Path

import av

from app.core.asr import asr
from app.jobs.models import Job
from app.jobs.store import JobStore
from app.pipelines.common import maybe_dub, should_stop_fn, translate_segments


class VideoProcessingError(Exception):
    pass


def _extract_audio(video_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_audio_path = output_dir / f"{video_path.stem}.wav"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(output_audio_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise VideoProcessingError(f"ffmpeg audio extraction failed: {result.stderr}")

    return output_audio_path


def _video_duration(video_path: Path) -> float | None:
    try:
        with av.open(str(video_path)) as container:
            if container.duration is not None:
                return float(container.duration) / 1_000_000
    except Exception:
        pass
    return None


def run(job: Job, store: JobStore) -> None:
    should_stop = should_stop_fn(store, job.id)

    store.update(job.id, status="extracting", stage="Extracting audio", progress=0.05)

    duration = _video_duration(job.input_file)
    if duration:
        store.update(job.id, duration_sec=duration)

    audio_path = _extract_audio(job.input_file, job.job_path / "tmp")

    if should_stop():
        raise InterruptedError("cancelled")

    store.update(job.id, status="transcribing", stage="Transcribing", progress=0.15)

    def on_asr_progress(fraction: float) -> None:
        store.update(job.id, progress=0.15 + fraction * 0.4)

    asr_result = asr.transcribe(
        audio_path,
        language=job.source_lang,
        duration_hint=duration,
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

    maybe_dub(job, store, segments, should_stop)
