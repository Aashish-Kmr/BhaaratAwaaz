from __future__ import annotations

import threading
from pathlib import Path

import torch
import soundfile as sf

from app import config


class TTSError(Exception):
    """Base exception for TTS errors."""


class TTS:
    """
    Text-to-speech dubbing via Indic Parler-TTS. Used only as a best-effort,
    non-blocking bonus artifact for finished audio jobs (see
    pipelines/audio.py) — never on the critical path to marking a job done,
    since it is by far the slowest stage on CPU.

    Heavy dependency (parler_tts + descript-audiotools) and the model itself
    (several GB) are imported/loaded lazily so the rest of the app works fine
    even if this stage is skipped or its deps aren't installed.
    """

    MODEL_NAME = "ai4bharat/indic-parler-tts"

    SPEAKERS = {"en": "Thoma", "hi": "Rohit", "mr": "Sanjay"}

    def __init__(self, device: str | None = None):
        self.device = device or config.TTS_DEVICE or (
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self._model = None
        self._tokenizer = None
        self._description_tokenizer = None
        self._lock = threading.Lock()

    def is_ready(self) -> bool:
        return self._model is not None

    def _load(self):
        if self._model is not None:
            return

        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer

        self._model = ParlerTTSForConditionalGeneration.from_pretrained(self.MODEL_NAME).to(
            self.device
        )
        self._tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
        self._description_tokenizer = AutoTokenizer.from_pretrained(
            self._model.config.text_encoder._name_or_path
        )

    def synthesize(self, text: str, language: str, output_path: str | Path) -> Path:
        if not text or not text.strip():
            raise TTSError("Text cannot be empty.")

        if language not in self.SPEAKERS:
            raise TTSError(f"Unsupported language: {language}")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        speaker = self.SPEAKERS[language]
        description = (
            f"{speaker}'s voice is clear and natural, speaking at a moderate speed "
            f"and pitch. The recording is very clear with no background noise."
        )

        with self._lock:
            self._load()

            description_input_ids = (
                self._description_tokenizer(description, return_tensors="pt")
                .input_ids.to(self.device)
            )

            prompt_inputs = self._tokenizer(text, return_tensors="pt")
            prompt_input_ids = prompt_inputs.input_ids.to(self.device)
            prompt_attention_mask = prompt_inputs.attention_mask.to(self.device)

            try:
                with torch.no_grad():
                    generation = self._model.generate(
                        input_ids=description_input_ids,
                        prompt_input_ids=prompt_input_ids,
                        prompt_attention_mask=prompt_attention_mask,
                    )

                audio = generation.cpu().numpy().squeeze()
                sf.write(output_path, audio, self._model.config.sampling_rate)
            except Exception as exc:
                raise TTSError(f"Failed to synthesize speech: {language}") from exc

        return output_path


tts = TTS()
