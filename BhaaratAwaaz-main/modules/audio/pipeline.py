from __future__ import annotations

import json
from pathlib import Path

from modules.audio.preprocessing import preprocess_audio
from modules.audio.asr import ASR
from modules.audio.translation import Translator
from modules.audio.tts import TTS
from shared.config import Config
from shared.logging import setup_logging


logger = setup_logging()


class PipelineError(Exception):
    """Base exception for pipeline errors."""


class AudioPipeline:

    SUPPORTED_LANGUAGES = {"en", "hi", "mr"}

    SUPPORTED_AUDIO_EXTENSIONS = {
        ".wav",
        ".mp3",
        ".m4a",
        ".flac",
        ".ogg",
        ".aac",
    }

    def __init__(
        self,
        asr_model: str = Config.ASR_MODEL,
        asr_device: str = Config.ASR_DEVICE,
        asr_compute_type: str = Config.ASR_COMPUTE_TYPE,
        translation_model_root: str = str(
            Config.TRANSLATION_MODEL_DIR
        ),
        translation_device: str = Config.TRANSLATION_DEVICE,
    ):

        self.asr = ASR(
            model_size=asr_model,
            device=asr_device,
            compute_type=asr_compute_type,
        )

        self.translator = Translator(
            model_root=translation_model_root,
            device=translation_device,
        )

        self.tts = TTS(
            device=Config.TTS_DEVICE,
        )

    def _validate_input(
        self,
        input_audio: str | Path,
    ) -> Path:

        path = Path(input_audio)

        if not path.exists():
            raise PipelineError(
                f"Input audio does not exist: {path}"
            )

        if not path.is_file():
            raise PipelineError(
                f"Input path is not a file: {path}"
            )

        if path.suffix.lower() not in self.SUPPORTED_AUDIO_EXTENSIONS:
            raise PipelineError(
                f"Unsupported audio format: {path.suffix}"
            )

        return path

    def _validate_language(
        self,
        language: str,
        name: str,
    ):

        if language not in self.SUPPORTED_LANGUAGES:
            raise PipelineError(
                f"Unsupported {name} language: {language}. "
                f"Supported languages: "
                f"{sorted(self.SUPPORTED_LANGUAGES)}"
            )

    def process(
        self,
        input_audio: str | Path,
        target_language: str,
        source_language: str | None = None,
    ) -> dict:

        Config.create_directories()

        input_audio = self._validate_input(
            input_audio
        )

        self._validate_language(
            target_language,
            "target",
        )

        if source_language is not None:
            self._validate_language(
                source_language,
                "source",
            )

        logger.info(
            "Starting audio pipeline | input=%s | target=%s",
            input_audio,
            target_language,
        )

        # --------------------------------------------------
        # 1. Preprocessing
        # --------------------------------------------------

        normalized_audio = preprocess_audio(
            input_path=input_audio,
            output_directory=Config.TEMP_DIR,
        )

        # --------------------------------------------------
        # 2. ASR
        # --------------------------------------------------

        asr_result = self.asr.transcribe(
            normalized_audio.output_path,
            language=source_language,
        )

        detected_language = asr_result["language"]

        self._validate_language(
            detected_language,
            "detected",
        )

        # --------------------------------------------------
        # 3. Translation
        # --------------------------------------------------

        translated_segments = (
            self.translator.translate_segments(
                segments=asr_result["segments"],
                source_language=detected_language,
                target_language=target_language,
            )
        )

        # ==================================================
        # 4. TTS
        # ==================================================

        translated_text = " ".join(
            segment["translated_text"]
            for segment in translated_segments
        )

        tts_output_path = (
            Config.OUTPUT_DIR
            / f"{input_audio.stem}_{target_language}.wav"
        )

        logger.info(
            "Starting TTS | language=%s | output=%s",
            target_language,
            tts_output_path,
        )

        self.tts.synthesize(
            text=translated_text,
            language=target_language,
            output_path=tts_output_path,
        )
        # --------------------------------------------------
        # 5. Output
        # --------------------------------------------------

        output_data = {
            "audio_file": str(
                input_audio.resolve()
            ),
            "normalized_audio": {
                "file": normalized_audio.output_path,
                "sample_rate": Config.SAMPLE_RATE,
                "channels": Config.CHANNELS,
                "format": Config.AUDIO_FORMAT,
            },
            "asr": {
                "model": self.asr.model_size,
                "device": self.asr.device,
                "compute_type": self.asr.compute_type,
                "language": detected_language,
                "language_probability": asr_result[
                    "language_probability"
                ],
            },
            "translation": {
                "source_language": detected_language,
                "target_language": target_language,
            },
            "tts": {
                "language": target_language,
                "output_file": str(tts_output_path),
            },

            "output_audio": str(tts_output_path),
            "segments": translated_segments,
        }

        output_path = (
            Config.OUTPUT_DIR
            / f"{input_audio.stem}_translation.json"
        )

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
            "Audio pipeline completed | output=%s",
            output_path,
        )

        output_data["output_file"] = str(
            output_path
        )

        return output_data