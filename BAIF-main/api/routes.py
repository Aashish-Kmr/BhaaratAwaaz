from pathlib import Path

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
)
from fastapi.responses import FileResponse

from config import OUTPUT_DIR, UPLOAD_DIR

from handlers.docx_handler import docx_handler
from handlers.pptx_handler import pptx_handler
from handlers.xlsx_handler import xlsx_handler
from handlers.csv_handler import csv_handler
from handlers.pdf_handler import pdf_handler


router = APIRouter()


# ==========================================================
# HEALTH
# ==========================================================

@router.get("/health")
def health():

    return {
        "status": "UP"
    }


# ==========================================================
# TRANSLATE
# ==========================================================

@router.post("/translate")
async def translate_file(
    file: UploadFile = File(...),
    target_language: str = Form(...),
):

    # ------------------------------------------------------
    # Validate target language
    # ------------------------------------------------------

    target_language = (
        target_language
        .strip()
        .lower()
    )

    if target_language not in (
        "en",
        "hi",
        "mr",
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported target language. "
                "Supported languages: en, hi, mr."
            ),
        )

    # ------------------------------------------------------
    # Validate filename
    # ------------------------------------------------------

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="Filename is required.",
        )

    original_filename = Path(
        file.filename
    ).name

    suffix = Path(
        original_filename
    ).suffix.lower()

    # ------------------------------------------------------
    # Supported file types
    # ------------------------------------------------------

    supported_extensions = {
        ".docx",
        ".pptx",
        ".xlsx",
        ".csv",
        ".pdf",
    }

    if suffix not in supported_extensions:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Supported files: "
                ".docx, .pptx, .xlsx, .csv, .pdf"
            ),
        )

    # ------------------------------------------------------
    # Input / output paths
    # ------------------------------------------------------

    input_path = (
        UPLOAD_DIR
        / original_filename
    )

    output_path = (
        OUTPUT_DIR
        / f"translated_{original_filename}"
    )

    # ------------------------------------------------------
    # Save uploaded file
    # ------------------------------------------------------

    try:

        with open(
            input_path,
            "wb",
        ) as output_file:

            while True:

                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                output_file.write(
                    chunk
                )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to save uploaded file: "
                f"{exc}"
            ),
        )

    # ------------------------------------------------------
    # Select appropriate handler
    # ------------------------------------------------------

    handlers = {
        ".docx": docx_handler,
        ".pptx": pptx_handler,
        ".xlsx": xlsx_handler,
        ".csv": csv_handler,
        ".pdf": pdf_handler,
    }

    handler = handlers.get(
        suffix
    )

    if handler is None:

        raise HTTPException(
            status_code=400,
            detail="Unsupported file type.",
        )

    # ------------------------------------------------------
    # Log translation request
    # ------------------------------------------------------

    print()
    print("=" * 60)
    print("TRANSLATION REQUEST")
    print("=" * 60)

    print(
        "File:",
        original_filename,
    )

    print(
        "File type:",
        suffix,
    )

    print(
        "Target language:",
        target_language,
    )

    print(
        "Source language:",
        "AUTO DETECT",
    )

    print("=" * 60)

    # ------------------------------------------------------
    # Translate
    #
    # IMPORTANT:
    #
    # source_language is intentionally NOT passed.
    #
    # TranslationService will automatically call:
    #
    # detect_language(text)
    # ------------------------------------------------------

    try:

        handler.translate(
            input_file=input_path,
            output_file=output_path,
            target_language=target_language,
        )

    except Exception as exc:

        print(
            "Translation failed:",
            repr(exc),
        )

        # --------------------------------------------------
        # Remove incomplete output if one was created
        # --------------------------------------------------

        if output_path.exists():

            try:
                output_path.unlink()
            except Exception:
                pass

        raise HTTPException(
            status_code=500,
            detail=(
                f"Translation failed: {exc}"
            ),
        )

    # ------------------------------------------------------
    # Verify output file
    # ------------------------------------------------------

    if not output_path.exists():

        raise HTTPException(
            status_code=500,
            detail=(
                "Translation completed but "
                "output file was not created."
            ),
        )

    # ------------------------------------------------------
    # Media types
    # ------------------------------------------------------

    media_types = {

        ".docx":
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",

        ".pptx":
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",

        ".xlsx":
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

        ".csv":
            "text/csv",

        ".pdf":
            "application/pdf",
    }

    # ------------------------------------------------------
    # Return translated file
    # ------------------------------------------------------

    return FileResponse(
        path=str(output_path),
        media_type=media_types[suffix],
        filename=output_path.name,
        headers={
            "Content-Disposition": (
                f'attachment; '
                f'filename="{output_path.name}"'
            ),
            "Cache-Control": "no-cache",
        },
    )