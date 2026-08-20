from pathlib import Path
import subprocess


def render_subtitled_video(
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
) -> Path:

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # FFmpeg subtitles filter needs escaped path
    subtitle_filter_path = (
        subtitle_path
        .resolve()
        .as_posix()
        .replace(":", r"\:")
        .replace("'", r"\'")
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"subtitles='{subtitle_filter_path}'",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "copy",
        str(output_path),
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Subtitle rendering failed:\n"
            + result.stderr[-5000:]
        )

    if not output_path.exists():
        raise RuntimeError(
            "FFmpeg completed but the "
            "translated video was not created."
        )

    return output_path