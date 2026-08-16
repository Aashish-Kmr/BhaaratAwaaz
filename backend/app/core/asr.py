from __future__ import annotations

import math
import threading
from pathlib import Path
from typing import Callable, Iterator

from faster_whisper import WhisperModel

from app import config


class ASRError(Exception):
    """Base exception for ASR-related errors."""


def _confidence_from_logprob(avg_logprob: float | None) -> float | None:
    if avg_logprob is None:
        return None
    return max(0.0, min(1.0, math.exp(avg_logprob)))


class ASR:
    """
    Speech-to-text via faster-whisper. Shared by the audio and video
    pipelines. Loaded lazily and reused for the process lifetime; a lock
    serializes calls since the app runs a single background worker anyway.
    """

    def __init__(
        self,
        model_size: str = config.ASR_MODEL,
        device: str = config.ASR_DEVICE,
        compute_type: str = config.ASR_COMPUTE_TYPE,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: WhisperModel | None = None
        self._lock = threading.Lock()

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def is_ready(self) -> bool:
        return self._model is not None

    def transcribe(
        self,
        audio_path: str | Path,
        language: str | None = None,
        duration_hint: float | None = None,
        on_progress: Callable[[float], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict:
        """
        Transcribe an audio file into timed segments.

        `on_progress(fraction)` is called after each segment using the
        segment's end time relative to `duration_hint`, so callers can surface
        incremental progress instead of a frozen bar during a long file.
        `should_stop()` lets callers cooperatively cancel between segments.
        """

        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        try:
            with self._lock:
                model = self._get_model()

                segments_gen, info = model.transcribe(
                    str(audio_path),
                    language=language,
                    vad_filter=config.VAD_ENABLED,
                    vad_parameters={"min_silence_duration_ms": config.VAD_MIN_SILENCE_MS},
                    beam_size=config.ASR_BEAM_SIZE,
                )

                duration = duration_hint or info.duration or 0.0

                transcript_segments = []

                for index, segment in enumerate(segments_gen, start=1):
                    transcript_segments.append(
                        {
                            "id": index,
                            "start": float(segment.start),
                            "end": float(segment.end),
                            "text": segment.text.strip(),
                            "confidence": _confidence_from_logprob(segment.avg_logprob),
                        }
                    )

                    if on_progress and duration > 0:
                        on_progress(min(1.0, segment.end / duration))

                    if should_stop and should_stop():
                        break

            return {
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": duration,
                "segments": transcript_segments,
            }

        except Exception as exc:
            raise ASRError(f"Failed to transcribe audio: {audio_path}") from exc


asr = ASR()
