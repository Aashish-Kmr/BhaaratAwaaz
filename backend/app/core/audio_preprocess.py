from __future__ import annotations

import av
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

MAX_AUDIO_DURATION_SECONDS = 30 * 60  # 30 minutes

TARGET_SAMPLE_RATE = 16_000
TARGET_CHANNELS = 1

SUPPORTED_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".webm", ".mp4",
}


class AudioProcessingError(Exception):
    """Base exception for audio processing errors."""


class AudioValidationError(AudioProcessingError):
    """Raised when an audio file is invalid."""


class AudioNormalizationError(AudioProcessingError):
    """Raised when audio normalization fails."""


@dataclass
class AudioMetadata:
    file_path: str
    duration_seconds: float
    sample_rate: Optional[int]
    channels: Optional[int]
    format: Optional[str]
    size_bytes: int


@dataclass
class NormalizedAudio:
    input_path: str
    output_path: str
    duration_seconds: float
    sample_rate: int
    channels: int
    format: str


def validate_file(audio_path: str | Path) -> Path:
    audio_path = Path(audio_path)

    if not audio_path.exists():
        raise AudioValidationError(f"Audio file does not exist: {audio_path}")
    if not audio_path.is_file():
        raise AudioValidationError(f"Path is not a file: {audio_path}")

    return audio_path


def get_audio_metadata(audio_path: str | Path) -> AudioMetadata:
    audio_path = validate_file(audio_path)

    try:
        container = av.open(str(audio_path))
    except Exception as exc:
        raise AudioValidationError(f"Unable to open audio file: {audio_path}") from exc

    try:
        audio_stream = next((s for s in container.streams if s.type == "audio"), None)

        if audio_stream is None:
            raise AudioValidationError(f"No audio stream found in: {audio_path}")

        duration_seconds = 0.0

        if audio_stream.duration is not None:
            duration_seconds = float(audio_stream.duration * float(audio_stream.time_base))
        elif container.duration is not None:
            duration_seconds = float(container.duration) / 1_000_000

        sample_rate = audio_stream.codec_context.sample_rate
        channels = audio_stream.codec_context.channels
        format_name = container.format.name if container.format is not None else None

        return AudioMetadata(
            file_path=str(audio_path.resolve()),
            duration_seconds=duration_seconds,
            sample_rate=sample_rate,
            channels=channels,
            format=format_name,
            size_bytes=audio_path.stat().st_size,
        )
    finally:
        container.close()


def validate_audio(audio_path: str | Path) -> AudioMetadata:
    metadata = get_audio_metadata(audio_path)

    if metadata.duration_seconds <= 0:
        raise AudioValidationError("Audio duration is zero or could not be determined.")

    if metadata.duration_seconds > MAX_AUDIO_DURATION_SECONDS:
        raise AudioValidationError(
            f"Audio duration is {metadata.duration_seconds / 60:.2f} minutes. "
            f"Maximum allowed duration is 30 minutes."
        )

    return metadata


def normalize_audio(input_path: str | Path, output_path: str | Path) -> NormalizedAudio:
    """Decode + resample to 16kHz mono PCM16 WAV using PyAV (no system ffmpeg)."""

    input_path = Path(input_path)
    output_path = Path(output_path)

    metadata = validate_audio(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        input_container = av.open(str(input_path))
    except Exception as exc:
        raise AudioNormalizationError(f"Unable to open input audio: {input_path}") from exc

    try:
        audio_stream = next((s for s in input_container.streams if s.type == "audio"), None)

        if audio_stream is None:
            raise AudioNormalizationError("No audio stream found.")

        output_container = av.open(str(output_path), mode="w", format="wav")

        try:
            output_stream = output_container.add_stream("pcm_s16le", rate=TARGET_SAMPLE_RATE)
            output_stream.layout = "mono"

            resampler = av.AudioResampler(format="s16", layout="mono", rate=TARGET_SAMPLE_RATE)

            for frame in input_container.decode(audio_stream):
                for resampled_frame in resampler.resample(frame):
                    for packet in output_stream.encode(resampled_frame):
                        output_container.mux(packet)

            for frame in resampler.resample(None):
                for packet in output_stream.encode(frame):
                    output_container.mux(packet)

            for packet in output_stream.encode():
                output_container.mux(packet)
        finally:
            output_container.close()

    except Exception as exc:
        if output_path.exists():
            output_path.unlink()
        if isinstance(exc, AudioNormalizationError):
            raise
        raise AudioNormalizationError(f"Failed to normalize audio: {input_path}") from exc
    finally:
        input_container.close()

    if not output_path.exists():
        raise AudioNormalizationError("Normalization completed but output file was not created.")

    return NormalizedAudio(
        input_path=str(input_path.resolve()),
        output_path=str(output_path.resolve()),
        duration_seconds=metadata.duration_seconds,
        sample_rate=TARGET_SAMPLE_RATE,
        channels=TARGET_CHANNELS,
        format="wav",
    )


def preprocess_audio(input_path: str | Path, output_directory: str | Path) -> NormalizedAudio:
    input_path = validate_file(input_path)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)

    output_path = output_directory / f"{input_path.stem}_normalized.wav"

    return normalize_audio(input_path=input_path, output_path=output_path)
