from __future__ import annotations

import json
from pathlib import Path

from .preprocessing import preprocess_audio
from .asr import ASR
from .translation import Translator
from .tts import TTS
from ...shared.config import Config
from ...shared.logging import setup_logging


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

        # TTS is constructed lazily rather than here: TTS.__init__ loads
        # the multi-GB Parler-TTS weights immediately, which would be paid
        # by every audio job even when dubbing is switched off -- and in a
        # build packaged without those weights it would fail outright.
        self._tts = None

    @property
    def tts(self) -> TTS:
        if self._tts is None:
            self._tts = TTS(
                device=Config.TTS_DEVICE,
            )
        return self._tts

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
        include_dubbing: bool = True,
        on_progress=None,
        should_stop=None,
        temp_dir: str | Path | None = None,
        output_dir: str | Path | None = None,
    ) -> dict:
        """
        Added parameters (all optional, defaults preserve the original
        behaviour):

        include_dubbing
            Run the TTS stage. False skips it entirely -- by far the
            slowest stage on CPU -- and leaves "tts"/"output_audio" unset.
        on_progress(fraction)
            Called at stage boundaries with 0.0-1.0 so a caller can drive
            a progress bar.
        should_stop()
            Polled at stage boundaries; returning True raises
            InterruptedError so a queued job can be cancelled mid-run.
        temp_dir / output_dir
            Override Config.TEMP_DIR / Config.OUTPUT_DIR per call, so
            concurrent or per-job runs don't share one global directory.
        """

        def report(fraction: float) -> None:
            if on_progress is not None:
                on_progress(fraction)

        def check_stop() -> None:
            if should_stop is not None and should_stop():
                raise InterruptedError("cancelled")

        Config.create_directories()

        temp_dir = Path(temp_dir) if temp_dir is not None else Config.TEMP_DIR
        output_dir = Path(output_dir) if output_dir is not None else Config.OUTPUT_DIR

        temp_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

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

        check_stop()
        report(0.05)

        normalized_audio = preprocess_audio(
            input_path=input_audio,
            output_directory=temp_dir,
        )

        # --------------------------------------------------
        # 2. ASR
        # --------------------------------------------------

        check_stop()
        report(0.15)

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

        check_stop()
        report(0.55)

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

        check_stop()
        report(0.95)

        translated_text = " ".join(
            segment["translated_text"]
            for segment in translated_segments
        )

        tts_output_path = (
            output_dir
            / f"{input_audio.stem}_{target_language}.wav"
        )

        if include_dubbing:

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

        else:

            logger.info(
                "Skipping TTS | dubbing not requested"
            )

            tts_output_path = None
        # --------------------------------------------------
        # 5. Output
        # --------------------------------------------------

        output_data = {
            "audio_file": str(
                input_audio.resolve()
            ),
            "normalized_audio": {
                "file": normalized_audio.output_path,
                # Added: preprocess_audio already measures this, and a
                # caller otherwise has to re-open the file to get it.
                "duration_seconds": normalized_audio.duration_seconds,
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
            "tts": (
                {
                    "language": target_language,
                    "output_file": str(tts_output_path),
                }
                if tts_output_path is not None
                else None
            ),

            "output_audio": (
                str(tts_output_path)
                if tts_output_path is not None
                else None
            ),
            "segments": translated_segments,
        }

        output_path = (
            output_dir
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

        report(1.0)

        return output_data