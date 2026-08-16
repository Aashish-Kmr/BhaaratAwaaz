from __future__ import annotations

from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from IndicTransToolkit.processor import IndicProcessor

from shared.config import Config
from shared.logging import setup_logging


logger = setup_logging()


class TranslationError(Exception):
    """Base exception for translation-related errors."""


class Translator:
    """
    Offline IndicTrans2 translation module.

    Supported:
        English ↔ Hindi
        English ↔ Marathi
        Hindi ↔ Marathi
    """

    MODEL_DIRS = {
        "en-indic": "indictrans2-en-indic-dist-200M",
        "indic-en": "indictrans2-indic-en-dist-200M",
        "indic-indic": "indictrans2-indic-indic-dist-320M",
    }

    LANGUAGES = {
        "en": "eng_Latn",
        "hi": "hin_Deva",
        "mr": "mar_Deva",
    }

    def __init__(
        self,
        model_root: str | Path = Config.TRANSLATION_MODEL_DIR,
        device: str = Config.TRANSLATION_DEVICE,
    ):
        self.model_root = Path(model_root)
        self.device = device

        self._models = {}
        self._tokenizers = {}
        self._processors = {}

    def _get_model_type(
        self,
        source_language: str,
        target_language: str,
    ) -> str:

        source_is_english = source_language == "en"
        target_is_english = target_language == "en"

        if source_is_english and not target_is_english:
            return "en-indic"

        if not source_is_english and target_is_english:
            return "indic-en"

        if not source_is_english and not target_is_english:
            return "indic-indic"

        raise TranslationError(
            "English → English translation is not supported."
        )

    def _load_model(self, model_type: str):

        if model_type in self._models:
            return (
                self._tokenizers[model_type],
                self._models[model_type],
                self._processors[model_type],
            )

        model_name = self.MODEL_DIRS[model_type]
        model_path = self.model_root / model_name

        if not model_path.exists():
            raise FileNotFoundError(
                f"IndicTrans2 model not found: {model_path}"
            )

        logger.info(
            "Loading translation model: %s",
            model_path,
        )

        tokenizer = AutoTokenizer.from_pretrained(
            str(model_path),
            trust_remote_code=True,
            local_files_only=True,
        )

        # CPU deployment → float32
        # GPU → float16
        dtype = (
            torch.float16
            if self.device == "cuda"
            else torch.float32
        )

        model = AutoModelForSeq2SeqLM.from_pretrained(
            str(model_path),
            trust_remote_code=True,
            torch_dtype=dtype,
            local_files_only=True,
        ).to(self.device)

        model.eval()

        processor = IndicProcessor(
            inference=True
        )

        self._tokenizers[model_type] = tokenizer
        self._models[model_type] = model
        self._processors[model_type] = processor

        return tokenizer, model, processor

    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> str:

        if not text or not text.strip():
            return ""

        if source_language not in self.LANGUAGES:
            raise TranslationError(
                f"Unsupported source language: "
                f"{source_language}"
            )

        if target_language not in self.LANGUAGES:
            raise TranslationError(
                f"Unsupported target language: "
                f"{target_language}"
            )

        if source_language == target_language:
            return text

        model_type = self._get_model_type(
            source_language,
            target_language,
        )

        tokenizer, model, processor = self._load_model(
            model_type
        )

        src_lang = self.LANGUAGES[source_language]
        tgt_lang = self.LANGUAGES[target_language]

        batch = processor.preprocess_batch(
            [text],
            src_lang=src_lang,
            tgt_lang=tgt_lang,
        )

        inputs = tokenizer(
            batch,
            truncation=True,
            padding="longest",
            return_tensors="pt",
            return_attention_mask=True,
        ).to(self.device)

        with torch.no_grad():
            generated_tokens = model.generate(
                **inputs,
                use_cache=True,
                min_length=0,
                max_length=256,
                num_beams=5,
                num_return_sequences=1,
            )

        generated_text = tokenizer.batch_decode(
            generated_tokens,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )

        translations = processor.postprocess_batch(
            generated_text,
            lang=tgt_lang,
        )

        return translations[0]

    def translate_segments(
        self,
        segments: list[dict],
        source_language: str,
        target_language: str,
    ) -> list[dict]:

        results = []

        for segment in segments:

            source_text = segment["text"]

            translated_text = self.translate(
                text=source_text,
                source_language=source_language,
                target_language=target_language,
            )

            results.append(
                {
                    "id": segment["id"],
                    "start": segment["start"],
                    "end": segment["end"],
                    "source_text": source_text,
                    "translated_text": translated_text,
                }
            )

        return results