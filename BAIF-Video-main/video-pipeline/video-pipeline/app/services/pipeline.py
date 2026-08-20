from pathlib import Path
import time
from datetime import datetime

from app.config import (
    TEMP_DIR,
    OUTPUT_DIR,
    LANGUAGE_CODES,
)

from app.services.media import (
    extract_audio,
)

from app.services.transcriber import (
    Transcriber,
)

from app.services.translator import (
    Translator,
)

from app.services.subtitles import (
    create_srt,
)

from app.services.renderer import (
    render_subtitled_video,
)


_transcriber = None
_translator = None


def get_transcriber():

    global _transcriber

    if _transcriber is None:
        _transcriber = Transcriber()

    return _transcriber


def get_translator():

    global _translator

    if _translator is None:
        _translator = Translator()

    return _translator


def process_video(
    video_path: Path,
    job_id: str,
    source_language: str,
    target_language: str,
    output_format: str = "both",
):

    # =========================================================
    # PIPELINE TIMER
    # =========================================================

    pipeline_start = time.perf_counter()

    def log_step(message: str):

        elapsed = (
            time.perf_counter()
            - pipeline_start
        )

        now = datetime.now().strftime(
            "%H:%M:%S"
        )

        print(
            f"[{now}] "
            f"[+{elapsed:8.2f}s] "
            f"{message}",
            flush=True,
        )

    log_step(
        "=================================================="
    )

    log_step(
        "PIPELINE STARTED"
    )

    log_step(
        f"Source: {source_language}"
    )

    log_step(
        f"Target: {target_language}"
    )

    log_step(
        f"Output format: {output_format}"
    )

    log_step(
        "=================================================="
    )

    # =========================================================
    # DIRECTORIES
    # =========================================================

    temp_dir = TEMP_DIR / job_id

    output_dir = OUTPUT_DIR / job_id

    temp_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # =========================================================
    # LANGUAGE CODES
    # =========================================================

    if source_language not in LANGUAGE_CODES:

        raise ValueError(
            f"Unsupported source language: "
            f"{source_language}"
        )

    if target_language not in LANGUAGE_CODES:

        raise ValueError(
            f"Unsupported target language: "
            f"{target_language}"
        )

    source_code = LANGUAGE_CODES[
        source_language
    ]

    target_code = LANGUAGE_CODES[
        target_language
    ]

    log_step(
        f"Language codes: "
        f"{source_code} -> {target_code}"
    )

    # =========================================================
    # 1. EXTRACT AUDIO
    # =========================================================

    step_start = time.perf_counter()

    audio_path = (
        temp_dir / "source.wav"
    )

    log_step(
        "STEP 1/6 - Extracting audio..."
    )

    extract_audio(
        video_path,
        audio_path,
    )

    step_time = (
        time.perf_counter()
        - step_start
    )

    log_step(
        f"Audio extraction complete "
        f"({step_time:.2f}s)"
    )

    log_step(
        f"Audio: {audio_path}"
    )

    # =========================================================
    # 2. TRANSCRIPTION
    # =========================================================

    step_start = time.perf_counter()

    log_step(
        "STEP 2/6 - Starting transcription..."
    )

    transcriber = get_transcriber()

    transcription = transcriber.transcribe(
        audio_path,
        source_code,
    )

    source_segments = transcription[
        "segments"
    ]

    if not source_segments:

        raise RuntimeError(
            "No speech was detected in the video."
        )

    step_time = (
        time.perf_counter()
        - step_start
    )

    detected_language = transcription.get(
        "language",
        source_code,
    )

    language_probability = (
        transcription.get(
            "language_probability",
            0.0,
        )
    )

    log_step(
        f"Transcription complete "
        f"({step_time:.2f}s)"
    )

    log_step(
        f"Transcription produced "
        f"{len(source_segments)} segments"
    )

    log_step(
        f"Detected language: "
        f"{detected_language} "
        f"({language_probability:.2f})"
    )

    # =========================================================
    # 3. CREATE SOURCE SUBTITLES
    # =========================================================

    step_start = time.perf_counter()

    source_srt = (
        output_dir / "source.srt"
    )

    log_step(
        "STEP 3/6 - Creating source SRT..."
    )

    create_srt(
        source_segments,
        source_srt,
    )

    step_time = (
        time.perf_counter()
        - step_start
    )

    log_step(
        f"Source SRT created "
        f"({step_time:.2f}s)"
    )

    log_step(
        f"Source SRT: {source_srt}"
    )

    # =========================================================
    # 4. TRANSLATION
    # =========================================================

    translated_segments = source_segments

    if source_code != target_code:

        step_start = time.perf_counter()

        log_step(
            "STEP 4/6 - Starting translation..."
        )

        log_step(
            f"Translation: "
            f"{source_code} -> {target_code}"
        )

        translator = get_translator()

        translated_segments = (
            translator.translate_segments(
                source_segments,
                source_language,
                target_language,
            )
        )

        step_time = (
            time.perf_counter()
            - step_start
        )

        log_step(
            f"Translation complete "
            f"({step_time:.2f}s)"
        )

        log_step(
            f"Translated "
            f"{len(translated_segments)} segments"
        )

    else:

        log_step(
            "STEP 4/6 - Source and target "
            "languages are identical."
        )

        log_step(
            "Translation skipped."
        )

    # =========================================================
    # 5. CREATE TRANSLATED SUBTITLES
    # =========================================================

    step_start = time.perf_counter()

    translated_srt = (
        output_dir / "translated.srt"
    )

    log_step(
        "STEP 5/6 - Creating translated SRT..."
    )

    create_srt(
        translated_segments,
        translated_srt,
    )

    step_time = (
        time.perf_counter()
        - step_start
    )

    log_step(
        f"Translated SRT created "
        f"({step_time:.2f}s)"
    )

    log_step(
        f"Translated SRT: "
        f"{translated_srt}"
    )

    # =========================================================
    # 6. OPTIONAL VIDEO RENDERING
    # =========================================================

    translated_video = None

    if output_format in {
        "video",
        "both",
    }:

        step_start = time.perf_counter()

        translated_video = (
            output_dir
            / "translated_video.mp4"
        )

        log_step(
            "STEP 6/6 - Rendering "
            "translated video..."
        )

        render_subtitled_video(
            video_path,
            translated_srt,
            translated_video,
        )

        step_time = (
            time.perf_counter()
            - step_start
        )

        log_step(
            f"Video rendering complete "
            f"({step_time:.2f}s)"
        )

        log_step(
            f"Translated video: "
            f"{translated_video}"
        )

    else:

        log_step(
            "STEP 6/6 - Video rendering skipped."
        )

        log_step(
            "Output mode: SRT only"
        )

    # =========================================================
    # FINAL RESULT
    # =========================================================

    total_time = (
        time.perf_counter()
        - pipeline_start
    )

    log_step(
        "=================================================="
    )

    log_step(
        f"PIPELINE COMPLETE "
        f"({total_time:.2f}s)"
    )

    log_step(
        f"TOTAL TIME: "
        f"{total_time / 60:.2f} minutes"
    )

    log_step(
        "=================================================="
    )

    # =========================================================
    # RETURN RESULT
    # =========================================================

    result = {

        "detected_language":
            detected_language,

        "source_srt":
            str(
                source_srt.resolve()
            ),

        "translated_srt":
            str(
                translated_srt.resolve()
            ),
    }

    if translated_video is not None:

        result[
            "translated_video"
        ] = str(
            translated_video.resolve()
        )

    return result