from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

from app.jobs.models import Job, Segment, new_job_id


class JobNotFound(Exception):
    pass


class JobStore:
    """
    Thread-safe in-memory job registry. Each job also owns a directory on
    disk (`jobs_dir/{id}/`) holding the uploaded input, any output artifacts,
    and a `segments.json` snapshot so segment edits survive a list refresh.

    Note: the job list itself is in-memory only and does not survive a
    process restart -- acceptable for a single-machine demo; files on disk
    are not cleaned up automatically on restart either.
    """

    def __init__(self, jobs_dir: Path):
        self._jobs_dir = jobs_dir
        self._jobs: dict[str, Job] = {}
        self._lock = threading.RLock()

    def new_job_dir(self) -> tuple[str, Path]:
        job_id = new_job_id()
        job_dir = self._jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_id, job_dir

    def add(self, job: Job) -> Job:
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFound(job_id)
        return job

    def try_get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            jobs = list(self._jobs.values())
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def update(self, job_id: str, **fields) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFound(job_id)
            for key, value in fields.items():
                setattr(job, key, value)
        return job

    def delete(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is None:
            raise JobNotFound(job_id)
        if job.job_path.exists():
            shutil.rmtree(job.job_path, ignore_errors=True)

    # ------------------------------------------------------------------
    # Segments
    # ------------------------------------------------------------------

    def save_segments(self, job_id: str, segments: list[Segment]) -> None:
        job = self.get(job_id)
        payload = [s.to_dict() if isinstance(s, Segment) else s for s in segments]
        job.segments_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.update(job_id, segment_count=len(payload))

    def load_segments(self, job_id: str) -> list[dict]:
        job = self.get(job_id)
        if not job.segments_file.exists():
            return []
        return json.loads(job.segments_file.read_text(encoding="utf-8"))
