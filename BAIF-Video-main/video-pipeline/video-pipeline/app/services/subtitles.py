from pathlib import Path

import pysrt


def seconds_to_time(
    seconds: float,
) -> pysrt.SubRipTime:

    milliseconds = int(
        round(seconds * 1000)
    )

    hours = milliseconds // 3_600_000
    milliseconds %= 3_600_000

    minutes = milliseconds // 60_000
    milliseconds %= 60_000

    secs = milliseconds // 1000
    milliseconds %= 1000

    return pysrt.SubRipTime(
        hours=hours,
        minutes=minutes,
        seconds=secs,
        milliseconds=milliseconds,
    )


def create_srt(
    segments: list[dict],
    output_path: Path,
) -> Path:

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    subtitles = pysrt.SubRipFile()

    for index, segment in enumerate(
        segments,
        start=1,
    ):

        subtitles.append(
            pysrt.SubRipItem(
                index=index,
                start=seconds_to_time(
                    segment["start"]
                ),
                end=seconds_to_time(
                    segment["end"]
                ),
                text=segment["text"],
            )
        )

    subtitles.save(
        str(output_path),
        encoding="utf-8",
    )

    return output_path