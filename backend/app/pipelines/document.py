"""
Document job adapter.

Thin bridge between the host job queue and the vendored BAIF-main
document pipeline (backend/vendor/docs_baif). All translation and
file-format logic lives there; this module only maps a Job onto the
handler call and reports progress/cancellation back to the store.
"""

from __future__ import annotations

from app.jobs.models import Job
from app.jobs.store import JobStore
from app.pipelines.common import should_stop_fn

from vendor.docs_baif.handlers.csv_handler import csv_handler
from vendor.docs_baif.handlers.docx_handler import docx_handler
from vendor.docs_baif.handlers.pdf_handler import pdf_handler
from vendor.docs_baif.handlers.pptx_handler import pptx_handler
from vendor.docs_baif.handlers.xlsx_handler import xlsx_handler
from vendor.docs_baif.services.translation_service import TranslationService

# The PDF handler takes differently-named arguments to the other four,
# which is why each entry carries its own call shape.
HANDLERS = {
    ".docx": docx_handler.translate_docx,
    ".pptx": pptx_handler.translate_pptx,
    ".xlsx": xlsx_handler.translate_xlsx,
    ".csv": csv_handler.translate_csv,
    ".pdf": pdf_handler.translate_pdf,
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

    action = HANDLERS.get(suffix)
    if action is None:
        raise ValueError(f"Unsupported document type: {suffix}")

    should_stop = should_stop_fn(store, job.id)

    store.update(job.id, status="extracting", stage="Reading document", progress=0.05)

    output_filename = f"translated_{input_path.stem}{suffix}"
    output_path = job.job_path / output_filename

    def on_progress(fraction: float) -> None:
        store.update(job.id, progress=0.1 + fraction * 0.85)

    store.update(job.id, status="translating", stage="Translating", progress=0.1)

    with TranslationService.hooks(on_progress=on_progress, should_stop=should_stop):
        if suffix == ".pdf":
            action(
                input_pdf_path=str(input_path),
                output_pdf_path=str(output_path),
                target_language=job.target_lang,
                source_language=job.source_lang,
            )
        else:
            action(
                input_path=str(input_path),
                output_path=str(output_path),
                target_language=job.target_lang,
                source_language=job.source_lang,
            )

    if should_stop():
        raise InterruptedError("cancelled")

    store.update(job.id, output_filename=output_filename)
