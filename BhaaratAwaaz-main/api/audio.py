from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse

from modules.audio.pipeline import AudioPipeline


router = APIRouter(
    prefix="/audio",
    tags=["Audio"],
)


BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = BASE_DIR / "data" / "input"
OUTPUT_DIR = BASE_DIR / "data" / "output"

INPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ------------------------------------------------------------
# Load pipeline once
# ------------------------------------------------------------

pipeline = AudioPipeline()


# ------------------------------------------------------------
# Supported values
# ------------------------------------------------------------

SUPPORTED_LANGUAGES = {
    "en",
    "hi",
    "mr",
}


SUPPORTED_AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
    ".aac",
}


# ============================================================
# POST /audio/translate
# ============================================================

@router.post("/translate")
async def translate_audio(
    audio_file: UploadFile = File(...),
    target_language: str = Form(...),
    source_language: str | None = Form(None),
):
    """
    Translate an uploaded audio file and return
    the generated speech audio.

    source_language:
        Optional.
        If omitted, ASR automatically detects it.

    target_language:
        Required.
        Supported:
            en
            hi
            mr
    """

    # --------------------------------------------------------
    # Validate target language
    # --------------------------------------------------------

    if target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported target language: "
                f"{target_language}. "
                f"Supported languages: "
                f"{sorted(SUPPORTED_LANGUAGES)}"
            ),
        )

    # --------------------------------------------------------
    # Validate source language
    # --------------------------------------------------------

    if source_language is not None:

        if source_language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported source language: "
                    f"{source_language}. "
                    f"Supported languages: "
                    f"{sorted(SUPPORTED_LANGUAGES)}"
                ),
            )

    # --------------------------------------------------------
    # Validate filename
    # --------------------------------------------------------

    if not audio_file.filename:
        raise HTTPException(
            status_code=400,
            detail="No audio filename provided.",
        )

    original_name = Path(audio_file.filename)

    if (
        original_name.suffix.lower()
        not in SUPPORTED_AUDIO_EXTENSIONS
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported audio format: "
                f"{original_name.suffix}"
            ),
        )

    # --------------------------------------------------------
    # Create unique input filename
    # --------------------------------------------------------

    file_id = uuid.uuid4().hex

    input_path = (
        INPUT_DIR
        / f"{file_id}_{original_name.name}"
    )

    try:

        # ----------------------------------------------------
        # Save uploaded audio
        # ----------------------------------------------------

        with input_path.open("wb") as buffer:

            shutil.copyfileobj(
                audio_file.file,
                buffer,
            )

        # ----------------------------------------------------
        # Run complete pipeline
        #
        # preprocessing
        #      ↓
        # ASR
        #      ↓
        # translation
        #      ↓
        # TTS
        #      ↓
        # translated WAV
        # ----------------------------------------------------

        result = pipeline.process(
            input_audio=input_path,
            target_language=target_language,
            source_language=source_language,
        )

        # ----------------------------------------------------
        # Get generated audio
        # ----------------------------------------------------

        output_path = Path(
            result["output_audio"]
        )

        if not output_path.exists():

            raise HTTPException(
                status_code=500,
                detail=(
                    "Pipeline completed but "
                    "output audio was not created."
                ),
            )

        # ----------------------------------------------------
        # Return generated WAV
        # ----------------------------------------------------

        return FileResponse(
            path=output_path,
            media_type="audio/wav",
            filename=(
                f"translated_"
                f"{original_name.stem}.wav"
            ),
            headers={
                "X-Source-Language": result[
                    "translation"
                ]["source_language"],

                "X-Target-Language": result[
                    "translation"
                ]["target_language"],
            },
        )

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Audio translation failed: {exc}"
            ),
        ) from exc