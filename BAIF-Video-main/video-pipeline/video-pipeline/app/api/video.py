from pathlib import Path
import shutil
import uuid

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from fastapi.responses import FileResponse

from app.config import (
    UPLOAD_DIR,
    OUTPUT_DIR,
)

from app.services.pipeline import (
    process_video,
)


router = APIRouter(
    prefix="/video",
    tags=["Video Pipeline"],
)


SUPPORTED_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
    ".wmv",
    ".flv",
}


SUPPORTED_LANGUAGES = {
    "english",
    "hindi",
    "marathi",
}


@router.post("/process")
async def process(
    file: UploadFile = File(...),
    source_language: str = Form(...),
    target_language: str = Form(...),
):

    # -----------------------------
    # Validate languages
    # -----------------------------

    if source_language not in (
        SUPPORTED_LANGUAGES
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported source language: "
                f"{source_language}"
            ),
        )

    if target_language not in (
        SUPPORTED_LANGUAGES
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported target language: "
                f"{target_language}"
            ),
        )

    # -----------------------------
    # Validate extension
    # -----------------------------

    filename = Path(
        file.filename or ""
    ).name

    extension = (
        Path(filename)
        .suffix
        .lower()
    )

    if extension not in (
        SUPPORTED_EXTENSIONS
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported video format: "
                f"{extension}"
            ),
        )

    # -----------------------------
    # Create job
    # -----------------------------

    job_id = str(
        uuid.uuid4()
    )

    job_upload_dir = (
        UPLOAD_DIR / job_id
    )

    job_upload_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    video_path = (
        job_upload_dir / filename
    )

    # -----------------------------
    # Save upload
    # -----------------------------

    try:

        with video_path.open(
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                file.file,
                buffer,
            )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to save "
                f"uploaded video: {exc}"
            ),
        )

    # -----------------------------
    # Process
    # -----------------------------

    try:

        result = process_video(
            video_path=video_path,
            job_id=job_id,
            source_language=source_language,
            target_language=target_language,
        )

        return {
            "job_id": job_id,
            "status": "completed",
            "source_language": source_language,
            "target_language": target_language,
            **result,
        }

    except Exception as e:
        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {e}",
        )


@router.get(
    "/{job_id}/source-srt"
)
def download_source_srt(
    job_id: str,
):

    path = (
        OUTPUT_DIR
        / job_id
        / "source.srt"
    )

    if not path.exists():

        raise HTTPException(
            status_code=404,
            detail="Source SRT not found.",
        )

    return FileResponse(
        path=str(path),
        media_type="application/x-subrip",
        filename="source.srt",
    )


@router.get(
    "/{job_id}/translated-srt"
)
def download_translated_srt(
    job_id: str,
):

    path = (
        OUTPUT_DIR
        / job_id
        / "translated.srt"
    )

    if not path.exists():

        raise HTTPException(
            status_code=404,
            detail="Translated SRT not found.",
        )

    return FileResponse(
        path=str(path),
        media_type="application/x-subrip",
        filename="translated.srt",
    )


@router.get(
    "/{job_id}/translated-video"
)
def download_translated_video(
    job_id: str,
):

    path = (
        OUTPUT_DIR
        / job_id
        / "translated_video.mp4"
    )

    if not path.exists():

        raise HTTPException(
            status_code=404,
            detail="Translated video not found.",
        )

    return FileResponse(
        path=str(path),
        media_type="video/mp4",
        filename="translated_video.mp4",
    )