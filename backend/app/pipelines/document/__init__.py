from __future__ import annotations

from pathlib import Path

from app.jobs.models import Job
from app.jobs.store import JobStore
from app.pipelines.common import should_stop_fn

from .csv_handler import csv_handler
from .docx_handler import docx_handler
from .pdf_handler import pdf_handler
from .pptx_handler import pptx_handler
from .xlsx_handler import xlsx_handler

HANDLERS = {
    ".docx": docx_handler,
    ".pptx": pptx_handler,
    ".xlsx": xlsx_handler,
    ".csv": csv_handler,
    ".pdf": pdf_handler,
}

MEDIA_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".pdf": "application/pdf",
}


def run(job: Job, store: JobStore) -> None:
    input_path = job.input_file
    suffix = input_path.suffix.lower()

    handler = HANDLERS.get(suffix)
    if handler is None:
        raise ValueError(f"Unsupported document type: {suffix}")

    store.update(job.id, status="extracting", stage="Reading document", progress=0.05)

    output_filename = f"translated_{input_path.stem}{suffix}"
    output_path = job.job_path / output_filename

    def on_progress(fraction: float) -> None:
        store.update(
            job.id,
            status="translating",
            stage="Translating",
            progress=0.1 + fraction * 0.85,
        )

    should_stop = should_stop_fn(store, job.id)

    store.update(job.id, status="translating", stage="Translating", progress=0.1)

    handler.translate(
        input_file=str(input_path),
        output_file=str(output_path),
        source_language=job.source_lang,
        target_language=job.target_lang,
        on_progress=on_progress,
        should_stop=should_stop,
    )

    if should_stop():
        raise InterruptedError("cancelled")

    store.update(job.id, output_filename=output_filename)
