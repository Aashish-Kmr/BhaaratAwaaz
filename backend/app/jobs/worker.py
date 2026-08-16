from __future__ import annotations

import queue
import threading
import traceback

from app.jobs.models import now_iso
from app.jobs.store import JobStore, JobNotFound
from app.pipelines import audio as audio_pipeline
from app.pipelines import document as document_pipeline
from app.pipelines import video as video_pipeline

PIPELINES = {
    "video": video_pipeline,
    "audio": audio_pipeline,
    "document": document_pipeline,
}


class Worker:
    """
    Single background worker: one job at a time, matching the frontend's own
    assumption that this runs on a resource-constrained single machine.
    """

    def __init__(self, store: JobStore):
        self.store = store
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def enqueue(self, job_id: str) -> None:
        self._queue.put(job_id)

    def _loop(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self._process(job_id)
            except Exception:
                traceback.print_exc()

    def _process(self, job_id: str) -> None:
        try:
            job = self.store.get(job_id)
        except JobNotFound:
            return

        if job.cancel_requested:
            self.store.update(job_id, status="cancelled", stage="Cancelled", finished_at=now_iso())
            return

        pipeline = PIPELINES.get(job.kind)
        if pipeline is None:
            self.store.update(
                job_id,
                status="failed",
                stage="Failed",
                error=f"Unsupported job kind: {job.kind}",
                finished_at=now_iso(),
            )
            return

        try:
            pipeline.run(job, self.store)
        except InterruptedError:
            self.store.update(job_id, status="cancelled", stage="Cancelled", finished_at=now_iso())
            return
        except JobNotFound:
            return
        except Exception as exc:
            traceback.print_exc()
            self.store.update(
                job_id,
                status="failed",
                stage="Failed",
                error=str(exc),
                finished_at=now_iso(),
            )
            return

        try:
            current = self.store.get(job_id)
        except JobNotFound:
            return

        if current.cancel_requested:
            self.store.update(job_id, status="cancelled", stage="Cancelled", finished_at=now_iso())
        else:
            self.store.update(
                job_id, status="done", stage="Ready", progress=1.0, finished_at=now_iso()
            )
