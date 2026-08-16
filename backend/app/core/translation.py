from __future__ import annotations

import threading
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from IndicTransToolkit.processor import IndicProcessor

from app import config

if config.TORCH_NUM_THREADS is not None:
    torch.set_num_threads(config.TORCH_NUM_THREADS)


class TranslationError(Exception):
    """Base exception for translation-related errors."""


class Translator:
    """
    Offline IndicTrans2 translation.

    Supports English <-> Hindi, English <-> Marathi, and Hindi <-> Marathi
    directly (no pivot needed) via three distilled model checkpoints:

        en-indic     : English -> Hindi/Marathi
        indic-en     : Hindi/Marathi -> English
        indic-indic  : Hindi <-> Marathi

    Models are downloaded once (see scripts/download_models.py) into
    config.TRANSLATION_MODEL_DIR and loaded lazily, one model type at a time,
    on first use. A single process-wide lock serializes `generate()` calls
    since the models are not safe for concurrent inference from multiple
    threads and the app only ever runs one job at a time anyway.
    """

    MODEL_DIRS = {
        "en-indic": "indictrans2-en-indic-dist-200M",
        "indic-en": "indictrans2-indic-en-dist-200M",
        "indic-indic": "indictrans2-indic-indic-dist-320M",
    }

    def __init__(
        self,
        model_root: str | Path = config.TRANSLATION_MODEL_DIR,
        device: str = config.TRANSLATION_DEVICE,
    ):
        self.model_root = Path(model_root)
        self.device = device

        self._models: dict[str, AutoModelForSeq2SeqLM] = {}
        self._tokenizers: dict[str, AutoTokenizer] = {}
        self._processors: dict[str, IndicProcessor] = {}
        self._lock = threading.Lock()

    def model_path(self, model_type: str) -> Path:
        return self.model_root / self.MODEL_DIRS[model_type]

    def is_ready(self) -> bool:
        return all(self.model_path(t).exists() for t in self.MODEL_DIRS)

    def _get_model_type(self, source_language: str, target_language: str) -> str:
        source_is_english = source_language == "en"
        target_is_english = target_language == "en"

        if source_is_english and not target_is_english:
            return "en-indic"
        if not source_is_english and target_is_english:
            return "indic-en"
        if not source_is_english and not target_is_english:
            return "indic-indic"

        raise TranslationError("English -> English translation is not supported.")

    def _load_model(self, model_type: str):
        if model_type in self._models:
            return (
                self._tokenizers[model_type],
                self._models[model_type],
                self._processors[model_type],
            )

        model_path = self.model_path(model_type)

        if not model_path.exists():
            raise FileNotFoundError(
                f"Translation model not found: {model_path}. "
                f"Run scripts/download_models.py first."
            )

        tokenizer = AutoTokenizer.from_pretrained(
            str(model_path),
            trust_remote_code=True,
            local_files_only=True,
        )

        dtype = torch.float16 if self.device == "cuda" else torch.float32

        model = AutoModelForSeq2SeqLM.from_pretrained(
            str(model_path),
            trust_remote_code=True,
            torch_dtype=dtype,
            local_files_only=True,
        ).to(self.device)

        model.eval()

        processor = IndicProcessor(inference=True)

        self._tokenizers[model_type] = tokenizer
        self._models[model_type] = model
        self._processors[model_type] = processor

        return tokenizer, model, processor

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        return self.translate_batch([text], source_language, target_language)[0]

    def translate_batch(
        self,
        texts: list[str],
        source_language: str,
        target_language: str,
        num_beams: int = config.TRANSLATION_NUM_BEAMS,
    ) -> list[str]:
        """
        Translate many texts in one (or few) model.generate() calls instead
        of one call per text. Tokenize/generate/decode overhead is paid once
        per batch rather than once per segment, which matters a lot for
        transcripts with many short segments (typical for speech) -- this is
        the main lever for making audio/video translation faster, since both
        pipelines already funnel through this same method.
        """

        if not texts:
            return []

        if source_language not in config.FLORES_CODES:
            raise TranslationError(f"Unsupported source language: {source_language}")
        if target_language not in config.FLORES_CODES:
            raise TranslationError(f"Unsupported target language: {target_language}")

        if source_language == target_language:
            return list(texts)

        # Empty/whitespace-only entries are passed through unchanged rather
        # than fed to the model, but keep their position in the output list.
        indices_to_translate = [i for i, t in enumerate(texts) if t and t.strip()]
        results = list(texts)

        if not indices_to_translate:
            return results

        model_type = self._get_model_type(source_language, target_language)
        src_lang = config.FLORES_CODES[source_language]
        tgt_lang = config.FLORES_CODES[target_language]

        with self._lock:
            tokenizer, model, processor = self._load_model(model_type)

            texts_to_translate = [texts[i] for i in indices_to_translate]

            for chunk_start in range(0, len(texts_to_translate), config.TRANSLATION_BATCH_SIZE):
                chunk = texts_to_translate[chunk_start : chunk_start + config.TRANSLATION_BATCH_SIZE]

                batch = processor.preprocess_batch(chunk, src_lang=src_lang, tgt_lang=tgt_lang)

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
                        num_beams=num_beams,
                        num_return_sequences=1,
                    )

                generated_text = tokenizer.batch_decode(
                    generated_tokens,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=True,
                )

                translated_chunk = processor.postprocess_batch(generated_text, lang=tgt_lang)

                for offset, translated in enumerate(translated_chunk):
                    results[indices_to_translate[chunk_start + offset]] = translated

        return results


translator = Translator()
