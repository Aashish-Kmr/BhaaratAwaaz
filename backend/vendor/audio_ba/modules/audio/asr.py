from __future__ import annotations
from logging import info
from ...shared.config import Config
from ...shared.logging import setup_logging

import json
from pathlib import Path

from faster_whisper import WhisperModel

logger = setup_logging()

class ASRError(Exception):
    """Base exception for ASR-related errors."""


class ASR:
    """
    Speech-to-text module for BhaaratAwaaz.

    Default configuration:
        Model       : faster-whisper medium
        Device      : CPU
        Compute     : INT8
        Beam size   : 5
        VAD         : Enabled
    """

    def __init__(
        self,
        model_size: str = Config.ASR_MODEL,
        device: str = Config.ASR_DEVICE,
        compute_type: str = Config.ASR_COMPUTE_TYPE,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )

    def transcribe(
        self,
        audio_path: str | Path,
        language: str | None = None,
    ) -> dict:
        logger.info(
            "Starting ASR | model=%s | device=%s | compute=%s | audio=%s",
            self.model_size,
            self.device,
            self.compute_type,
            audio_path,
        )
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(
                f"Audio file not found: {audio_path}"
            )

        if not audio_path.is_file():
            raise ASRError(
                f"Audio path is not a file: {audio_path}"
            )

        try:
            segments, info = self.model.transcribe(
                str(audio_path),

                language=language,

                vad_filter=Config.VAD_ENABLED,

                vad_parameters={
                    "min_silence_duration_ms":
                        Config.VAD_MIN_SILENCE_MS,
                },

                beam_size=Config.ASR_BEAM_SIZE,

                # Added: guards against Whisper repetition loops (the
                # "... लिए लिए लिए लिए" failure). This pipeline previously
                # passed none of these and so inherited the library
                # defaults, of which condition_on_previous_text=True is the
                # dangerous one -- it feeds each segment's output back in as
                # context, so once a loop starts it reinforces itself
                # across the rest of the file. The video pipeline already
                # disabled it for exactly this reason.
                condition_on_previous_text=False,

                # Forbid any 3-gram from repeating and mildly penalise
                # repeated tokens.
                no_repeat_ngram_size=3,
                repetition_penalty=1.15,
            )

            transcript_segments = []

            # segments is a generator, so iteration
            # triggers the actual transcription.
            for index, segment in enumerate(segments, start=1):
                transcript_segments.append(
                    {
                        "id": index,
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text.strip(),
                    }
                )

            return {
                "language": info.language,
                "language_probability": info.language_probability,
                "segments": transcript_segments,
            }

        except Exception as exc:
            raise ASRError(
                f"Failed to transcribe audio: {audio_path}"
            ) from exc

    def transcribe_to_json(
        self,
        audio_path: str | Path,
        output_path: str | Path,
        language: str | None = None,
    ) -> dict:

        output_path = Path(output_path)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        result = self.transcribe(
            audio_path=audio_path,
            language=language,
        )

        output_data = {
            "audio_file": str(
                Path(audio_path).resolve()
            ),
            "model": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "language": result["language"],
            "language_probability": result[
                "language_probability"
            ],
            "segments": result["segments"],
        }

        with output_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                output_data,
                file,
                ensure_ascii=False,
                indent=2,
            )
        logger.info(
            "ASR completed | language=%s | probability=%.3f | segments=%d",
            info.language,
            info.language_probability,
            len(transcript_segments),
        )
        return output_data