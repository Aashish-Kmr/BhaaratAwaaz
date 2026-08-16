from pathlib import Path
import pysrt


def _seconds_to_time(seconds: float) -> pysrt.SubRipTime:
    ms = int(seconds * 1000)
    hours = ms // 3_600_000
    ms %= 3_600_000
    minutes = ms // 60_000
    ms %= 60_000
    secs = ms // 1000
    ms %= 1000
    return pysrt.SubRipTime(hours=hours, minutes=minutes, seconds=secs, milliseconds=ms)


def generate_srt(
    segments: list[dict],
    output_dir: str | Path,
    filename: str = "subtitles.srt",
) -> str:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    srt_path = output_dir / filename

    subs = pysrt.SubRipFile()

    for i, seg in enumerate(segments, start=1):
        item = pysrt.SubRipItem(
            index=i,
            start=_seconds_to_time(seg["start"]),
            end=_seconds_to_time(seg["end"]),
            text=seg["source_text"],
        )
        subs.append(item)

    subs.save(str(srt_path), encoding="utf-8")
    return str(srt_path)