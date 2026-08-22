from __future__ import annotations

from pathlib import Path

import torch
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
)

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

    Optimized for CPU batch translation.
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

        self.batch_size = Config.TRANSLATION_BATCH_SIZE
        self.beam_size = Config.TRANSLATION_BEAM_SIZE
        self.max_length = Config.TRANSLATION_MAX_LENGTH
        self.min_length = Config.TRANSLATION_MIN_LENGTH
        self.do_sample = Config.TRANSLATION_DO_SAMPLE

        # ----------------------------------------------------
        # Model caches
        # ----------------------------------------------------

        self._models = {}
        self._tokenizers = {}
        self._processors = {}

    # ========================================================
    # Model selection
    # ========================================================

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

        if (
            not source_is_english
            and not target_is_english
        ):
            return "indic-indic"

        raise TranslationError(
            "English → English translation is not supported."
        )

    # ========================================================
    # Load model
    # ========================================================

    def _load_model(self, model_type: str):

        # ----------------------------------------------------
        # IMPORTANT:
        # Model is loaded only once.
        # ----------------------------------------------------

        if model_type in self._models:

            return (
                self._tokenizers[model_type],
                self._models[model_type],
                self._processors[model_type],
            )

        model_name = self.MODEL_DIRS[model_type]

        model_path = (
            self.model_root / model_name
        )

        if not model_path.exists():

            raise FileNotFoundError(
                f"IndicTrans2 model not found: "
                f"{model_path}"
            )

        logger.info(
            "Loading translation model: %s",
            model_path,
        )

        # ----------------------------------------------------
        # Tokenizer
        # ----------------------------------------------------

        tokenizer = AutoTokenizer.from_pretrained(
            str(model_path),
            trust_remote_code=True,
            local_files_only=True,
        )

        # ----------------------------------------------------
        # Model dtype
        # ----------------------------------------------------

        if self.device == "cuda":
            dtype = torch.float16
        else:
            dtype = torch.float32

        # ----------------------------------------------------
        # Model
        # ----------------------------------------------------

        model = AutoModelForSeq2SeqLM.from_pretrained(
            str(model_path),
            trust_remote_code=True,
            torch_dtype=dtype,
            local_files_only=True,
        )

        model = model.to(self.device)

        model.eval()

        # ----------------------------------------------------
        # Processor
        # ----------------------------------------------------

        processor = IndicProcessor(
            inference=True
        )

        # ----------------------------------------------------
        # Cache everything
        # ----------------------------------------------------

        self._tokenizers[model_type] = tokenizer
        self._models[model_type] = model
        self._processors[model_type] = processor

        logger.info(
            "Translation model loaded | type=%s | device=%s",
            model_type,
            self.device,
        )

        return (
            tokenizer,
            model,
            processor,
        )

    # ========================================================
    # Single text translation
    # ========================================================

    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> str:

        if not text or not text.strip():
            return ""

        results = self.translate_batch(
            texts=[text],
            source_language=source_language,
            target_language=target_language,
        )

        return results[0]

    # ========================================================
    # Batch translation
    # ========================================================

    def translate_batch(
        self,
        texts: list[str],
        source_language: str,
        target_language: str,
    ) -> list[str]:

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

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

        if not texts:
            return []

        # ----------------------------------------------------
        # Same language
        # ----------------------------------------------------

        if source_language == target_language:
            return texts

        # ----------------------------------------------------
        # Select model
        # ----------------------------------------------------

        model_type = self._get_model_type(
            source_language,
            target_language,
        )

        tokenizer, model, processor = (
            self._load_model(model_type)
        )

        src_lang = self.LANGUAGES[
            source_language
        ]

        tgt_lang = self.LANGUAGES[
            target_language
        ]

        # ----------------------------------------------------
        # Remove empty text
        # ----------------------------------------------------

        cleaned_texts = [
            text.strip()
            if text
            else ""
            for text in texts
        ]

        # ----------------------------------------------------
        # IndicTrans preprocessing
        # ----------------------------------------------------

        batch = processor.preprocess_batch(
            cleaned_texts,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
        )

        # ----------------------------------------------------
        # Tokenization
        # ----------------------------------------------------

        inputs = tokenizer(
            batch,
            truncation=True,
            padding=True,
            return_tensors="pt",
            return_attention_mask=True,
        )

        # ----------------------------------------------------
        # Move tensors to device
        # ----------------------------------------------------

        inputs = {
            key: value.to(self.device)
            for key, value in inputs.items()
        }

        # ----------------------------------------------------
        # Inference
        # ----------------------------------------------------

        with torch.inference_mode():

            generated_tokens = model.generate(
                **inputs,

                use_cache=True,

                min_length=self.min_length,

                max_length=self.max_length,

                num_beams=self.beam_size,

                num_return_sequences=1,

                do_sample=self.do_sample,
            )

        # ----------------------------------------------------
        # Decode
        # ----------------------------------------------------

        generated_text = tokenizer.batch_decode(
            generated_tokens,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )

        # ----------------------------------------------------
        # IndicTrans postprocessing
        # ----------------------------------------------------

        translations = processor.postprocess_batch(
            generated_text,
            lang=tgt_lang,
        )

        return translations

    # ========================================================
    # Translate large segment list
    # ========================================================

    def translate_segments(
        self,
        segments: list[dict],
        source_language: str,
        target_language: str,
    ) -> list[dict]:

        if not segments:
            return []

        # ----------------------------------------------------
        # Extract text
        # ----------------------------------------------------

        source_texts = [
            segment["text"].strip()
            for segment in segments
        ]

        logger.info(
            "Translating %d segments | %s -> %s | batch_size=%d | beams=%d",
            len(source_texts),
            source_language,
            target_language,
            self.batch_size,
            self.beam_size,
        )

        # ----------------------------------------------------
        # Translate in batches
        # ----------------------------------------------------

        translated_texts = []

        total_segments = len(source_texts)

        for start in range(
            0,
            total_segments,
            self.batch_size,
        ):

            end = min(
                start + self.batch_size,
                total_segments,
            )

            batch_texts = source_texts[
                start:end
            ]

            logger.debug(
                "Translation batch %d-%d / %d",
                start + 1,
                end,
                total_segments,
            )

            batch_translations = (
                self.translate_batch(
                    texts=batch_texts,
                    source_language=source_language,
                    target_language=target_language,
                )
            )

            translated_texts.extend(
                batch_translations
            )

        # ----------------------------------------------------
        # Build final segment objects
        # ----------------------------------------------------

        results = []

        for segment, translated_text in zip(
            segments,
            translated_texts,
        ):

            results.append(
                {
                    "id": segment["id"],
                    "start": segment["start"],
                    "end": segment["end"],
                    "source_text": segment["text"],
                    "translated_text": translated_text,
                }
            )

        logger.info(
            "Translation completed | segments=%d",
            len(results),
        )

        return results