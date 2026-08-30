"""
Video job adapter.

Thin bridge between the host job queue and the vendored BAIF-Video-main
pipeline (backend/vendor/video_baif). Audio extraction, transcription,
NLLB translation, SRT generation and subtitle burn-in all live there.

The job itself stops at the SRT stage: burn-in is deliberately NOT part
of the job. It is a separate, on-demand step (see render_burned_in
below) so the expensive ffmpeg re-encode runs against the subtitles the
user has actually reviewed and corrected, rather than the raw machine
transcript.
"""

from __future__ import annotations

from pathlib import Path

from app.jobs.models import Job, Segment
from app.jobs.store import JobStore
from app.pipelines.common import should_stop_fn

from vendor.video_baif.services.pipeline import process_video
from vendor.video_baif.services.renderer import render_subtitled_video
from vendor.video_baif.services.subtitles import create_srt

# The vendored pipeline takes full language names ("marathi"), not the
# two-letter codes the rest of this app uses.
LANGUAGE_NAMES = {
    "mr": "marathi",
    "hi": "hindi",
    "en": "english",
}


def run(job: Job, store: JobStore) -> None:
    should_stop = should_stop_fn(store, job.id)

    store.update(job.id, status="extracting", stage="Extracting audio", progress=0.05)

    def on_progress(fraction: float) -> None:
        if fraction < 0.15:
            status, stage = "extracting", "Extracting audio"
        elif fraction < 0.55:
            status, stage = "transcribing", "Transcribing"
        else:
            status, stage = "translating", "Translating"

        store.update(job.id, status=status, stage=stage, progress=fraction)

    result = process_video(
        video_path=job.input_file,
        job_id=job.id,
        source_language=LANGUAGE_NAMES[job.source_lang],
        target_language=LANGUAGE_NAMES[job.target_lang],
        # Stop at SRT -- burn-in happens later, on demand.
        output_format="srt",
        on_progress=on_progress,
        should_stop=should_stop,
    )

    source_segments = result["source_segments"]
    translated_segments = result["translated_segments"]

    segments = [
        Segment(
            id=f"{job.id}_s{index}",
            start=source["start"],
            end=source["end"],
            source=source["text"],
            target=translated["text"],
        )
        for index, (source, translated) in enumerate(
            zip(source_segments, translated_segments)
        )
    ]

    store.save_segments(job.id, segments)

    store.update(
        job.id,
        subtitle_srt_path=result["translated_srt"],
        duration_sec=segments[-1].end if segments else None,
    )


def render_burned_in(job: Job, store: JobStore) -> Path:
    """
    Burn the job's current (possibly user-edited) subtitles into a copy
    of the video. Called on demand from the API, not by the worker.

    Re-generates the SRT from the saved segments first, so edits made in
    the subtitle editor are what actually get burned in.
    """

    segments = store.load_segments(job.id)

    if not segments:
        raise ValueError("This job has no subtitles to burn in.")

    srt_path = job.job_path / "burned_in.srt"

    create_srt(
        [
            {
                "start": segment["start"],
                "end": segment["end"],
                "text": segment.get("target") or segment.get("source") or "",
            }
            for segment in segments
        ],
        srt_path,
    )

    output_path = job.burned_in_video_file

    render_subtitled_video(
        job.input_file,
        srt_path,
        output_path,
    )

    return output_path
