from pathlib import Path
import subprocess


SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
    ".wmv",
    ".flv",
}


def extract_audio(
    video_path: Path,
    audio_path: Path,
) -> Path:

    audio_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(audio_path),
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg audio extraction failed:\n"
            + result.stderr[-5000:]
        )

    if not audio_path.exists():
        raise RuntimeError(
            "Audio extraction completed but "
            "the WAV file was not created."
        )

    return audio_path