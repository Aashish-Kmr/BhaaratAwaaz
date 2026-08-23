from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path

STATUSES = {
    "queued",
    "extracting",
    "transcribing",
    "translating",
    "dubbing",
    "done",
    "failed",
    "cancelled",
}

TERMINAL_STATUSES = {"done", "failed", "cancelled"}


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:12]}"


@dataclass
class Segment:
    id: str
    start: float
    end: float
    source: str
    target: str
    confidence: float | None = None
    edited: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Job:
    id: str
    filename: str
    kind: str  # video | audio | document
    bytes: int
    source_lang: str
    target_lang: str
    status: str = "queued"
    progress: float = 0.0
    stage: str = "Queued"
    duration_sec: float | None = None
    created_at: str = field(default_factory=now_iso)
    finished_at: str | None = None
    error: str | None = None
    segment_count: int = 0
    include_dubbing: bool = False
    dubbed_audio_ready: bool = False

    # Internal, not exposed in the public API shape.
    input_path: str = ""
    job_dir: str = ""
    cancel_requested: bool = False
    output_filename: str | None = None

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "kind": self.kind,
            "bytes": self.bytes,
            "durationSec": self.duration_sec,
            "sourceLang": self.source_lang,
            "targetLang": self.target_lang,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "createdAt": self.created_at,
            "finishedAt": self.finished_at,
            "error": self.error,
            "segmentCount": self.segment_count,
            "includeDubbing": self.include_dubbing,
            "dubbedAudioReady": self.dubbed_audio_ready,
        }

    @property
    def job_path(self) -> Path:
        return Path(self.job_dir)

    @property
    def input_file(self) -> Path:
        return Path(self.input_path)

    @property
    def segments_file(self) -> Path:
        return self.job_path / "segments.json"

    @property
    def output_file(self) -> Path | None:
        """Translated document output — path set by the document pipeline."""
        if not self.output_filename:
            return None
        return self.job_path / self.output_filename

    @property
    def dubbed_audio_file(self) -> Path:
        return self.job_path / "dubbed.wav"
