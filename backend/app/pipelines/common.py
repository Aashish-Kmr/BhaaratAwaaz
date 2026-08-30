from __future__ import annotations

from typing import Callable

from app.jobs.store import JobStore


def should_stop_fn(store: JobStore, job_id: str) -> Callable[[], bool]:
    """
    Build the cancellation predicate handed to the vendored pipelines.

    Returns True once the job has been cancelled (or deleted outright),
    which the pipelines poll at their stage boundaries.
    """

    def check() -> bool:
        job = store.try_get(job_id)
        return job is None or job.cancel_requested

    return check
