from __future__ import annotations

from pathlib import Path

import torch
import soundfile as sf

from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer


class TTSError(Exception):
    """Base exception for TTS errors."""


class TTS:
    """
    Text-to-Speech module for BhaaratAwaaz.

    Supports:
        en - English
        hi - Hindi
        mr - Marathi
    """

    SUPPORTED_LANGUAGES = {
        "en",
        "hi",
        "mr",
    }

    MODEL_NAME = "ai4bharat/indic-parler-tts"

    SPEAKERS = {
        "en": "Thoma",
        "hi": "Rohit",
        "mr": "Sanjay",
    }

    def __init__(
        self,
        device: str | None = None,
    ):

        self.device = device or (
            "cuda" if torch.cuda.is_available()
            else "cpu"
        )

        self.model = (
            ParlerTTSForConditionalGeneration
            .from_pretrained(self.MODEL_NAME)
            .to(self.device)
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.MODEL_NAME
        )

        self.description_tokenizer = AutoTokenizer.from_pretrained(
            self.model.config.text_encoder._name_or_path
        )

    def synthesize(
        self,
        text: str,
        language: str,
        output_path: str | Path,
    ) -> Path:

        if not text or not text.strip():
            raise TTSError(
                "Text cannot be empty."
            )

        if language not in self.SUPPORTED_LANGUAGES:
            raise TTSError(
                f"Unsupported language: {language}"
            )

        output_path = Path(output_path)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        speaker = self.SPEAKERS[language]

        description = (
            f"{speaker}'s voice is clear and natural, "
            f"speaking at a moderate speed and pitch. "
            f"The recording is very clear with no "
            f"background noise."
        )

        try:

            description_input_ids = (
                self.description_tokenizer(
                    description,
                    return_tensors="pt",
                )
                .input_ids
                .to(self.device)
            )

            prompt_inputs = self.tokenizer(
                text,
                return_tensors="pt",
            )

            prompt_input_ids = prompt_inputs.input_ids.to(
                self.device
            )

            prompt_attention_mask = prompt_inputs.attention_mask.to(
                self.device
            )

            with torch.no_grad():

                generation = self.model.generate(
                    input_ids=description_input_ids,
                    prompt_input_ids=prompt_input_ids,
                    prompt_attention_mask=prompt_attention_mask,
                )

            audio = (
                generation
                .cpu()
                .numpy()
                .squeeze()
            )

            sf.write(
                output_path,
                audio,
                self.model.config.sampling_rate,
            )

        except Exception as exc:

            raise TTSError(
                f"Failed to synthesize speech: "
                f"{language}"
            ) from exc

        return output_path