from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
import uuid

from app.services.extractor import extract_audio_from_video
from app.services.transcriber import transcribe_audio
from app.services.subtitles import generate_srt

router = APIRouter(prefix="/video", tags=["Video Pipeline"])

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
TEMP_DIR = BASE_DIR / "temp"

for d in [UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@router.post("/process")
async def process_video(
    file: UploadFile = File(...),
    source_language: str = Form("mr"),
):
    job_id = str(uuid.uuid4())
    job_upload_dir = UPLOAD_DIR / job_id
    job_output_dir = OUTPUT_DIR / job_id
    job_temp_dir = TEMP_DIR / job_id

    job_upload_dir.mkdir(parents=True, exist_ok=True)
    job_output_dir.mkdir(parents=True, exist_ok=True)
    job_temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        input_video_path = job_upload_dir / file.filename

        with open(input_video_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        audio_path = extract_audio_from_video(
            video_path=input_video_path,
            output_dir=job_temp_dir,
        )

        transcript_segments = transcribe_audio(
            audio_path=audio_path,
            source_language=source_language,
        )

        srt_path = generate_srt(
            segments=transcript_segments,
            output_dir=job_output_dir,
            filename=f"{Path(file.filename).stem}.srt",
        )

        return {
            "job_id": job_id,
            "status": "completed",
            "original_video": str(input_video_path),
            "extracted_audio": str(audio_path),
            "subtitle_file": str(srt_path),
            "segments": transcript_segments,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/subtitles")
def download_subtitles(job_id: str):
    job_output_dir = OUTPUT_DIR / job_id

    if not job_output_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="Job output directory not found"
        )

    subtitle_files = list(job_output_dir.glob("*.srt"))

    if not subtitle_files:
        raise HTTPException(
            status_code=404,
            detail="Subtitle file not found for this job"
        )

    subtitle_file = subtitle_files[0]

    return FileResponse(
        path=subtitle_file,
        media_type="application/x-subrip",
        filename=subtitle_file.name,
    )