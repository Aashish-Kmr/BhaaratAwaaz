import os
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
)

from .config import (
    EN_INDIC_MODEL_PATH,
    INDIC_EN_MODEL_PATH,
    LANGUAGE_CODES,
)

# Optimize CPU operations across all available physical cores
if not torch.cuda.is_available():
    torch.set_num_threads(os.cpu_count() or 4)


class Translator:

    def __init__(self):
        print("Creating Translator...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        print(f"Device: {self.device} ({self.dtype})")

        # ------------------------------------------------
        # Models are loaded lazily
        # ------------------------------------------------
        self.en_indic_model = None
        self.en_indic_tokenizer = None

        self.indic_en_model = None
        self.indic_en_tokenizer = None

        # ------------------------------------------------
        # Translation cache
        # ------------------------------------------------
        self.cache = {}

    # ====================================================
    # ENGLISH -> INDIC MODEL
    # ====================================================

    def load_en_indic_model(self):
        if self.en_indic_model is not None:
            return

        print("\nLoading IndicTrans2 EN -> Indic model...")
        print("Path:", EN_INDIC_MODEL_PATH)

        self.en_indic_tokenizer = AutoTokenizer.from_pretrained(
            str(EN_INDIC_MODEL_PATH),
            trust_remote_code=True,
        )

        self.en_indic_model = AutoModelForSeq2SeqLM.from_pretrained(
            str(EN_INDIC_MODEL_PATH),
            torch_dtype=self.dtype,
            trust_remote_code=True,
        ).to(self.device)

        self.en_indic_model.eval()
        print("EN -> Indic model loaded.")

    # ====================================================
    # INDIC -> ENGLISH MODEL
    # ====================================================

    def load_indic_en_model(self):
        if self.indic_en_model is not None:
            return

        print("\nLoading IndicTrans2 Indic -> EN model...")
        print("Path:", INDIC_EN_MODEL_PATH)

        self.indic_en_tokenizer = AutoTokenizer.from_pretrained(
            str(INDIC_EN_MODEL_PATH),
            trust_remote_code=True,
        )

        self.indic_en_model = AutoModelForSeq2SeqLM.from_pretrained(
            str(INDIC_EN_MODEL_PATH),
            torch_dtype=self.dtype,
            trust_remote_code=True,
        ).to(self.device)

        self.indic_en_model.eval()
        print("Indic -> EN model loaded.")

    # ====================================================
    # MAIN TRANSLATE METHOD
    # ====================================================

    def translate(
        self,
        text,
        source_language,
        target_language,
    ):
        if not text or not text.strip():
            return text

        source_language = source_language.lower()
        target_language = target_language.lower()

        if source_language == target_language:
            return text

        supported_languages = {"en", "hi", "mr"}
        if source_language not in supported_languages:
            raise ValueError(f"Unsupported source language: {source_language}")
        if target_language not in supported_languages:
            raise ValueError(f"Unsupported target language: {target_language}")

        key = (text, source_language, target_language)
        if key in self.cache:
            return self.cache[key]

        print(f"Translation request: {source_language} -> {target_language}")

        # English -> Indic
        if source_language == "en":
            result = self.translate_en_to_indic([text], target_language)[0]

        # Indic -> English
        elif target_language == "en":
            result = self.translate_indic_to_en([text], source_language)[0]

        # Indic -> English -> Indic (Pivot Translation)
        else:
            print(f"Using pivot translation: {source_language} -> en -> {target_language}")
            english_text = self.translate_indic_to_en([text], source_language)[0]
            result = self.translate_en_to_indic([english_text], target_language)[0]

        self.cache[key] = result
        return result

    # ====================================================
    # BATCH TRANSLATE
    # ====================================================

    def translate_batch(
        self,
        texts,
        source_language,
        target_language,
    ):
        if not texts:
            return []

        indexed_texts = []
        for index, text in enumerate(texts):
            if text is None or not str(text).strip():
                continue
            indexed_texts.append((index, str(text)))

        if not indexed_texts:
            return list(texts)

        clean_texts = [item[1] for item in indexed_texts]
        source_language = source_language.lower()
        target_language = target_language.lower()

        if source_language == target_language:
            return list(texts)

        # English -> Indic
        if source_language == "en" and target_language in ("hi", "mr"):
            translated = self.translate_en_to_indic(clean_texts, target_language)

        # Indic -> English
        elif source_language in ("hi", "mr") and target_language == "en":
            translated = self.translate_indic_to_en(clean_texts, source_language)

        # Pivot batch: Indic -> English -> Indic
        elif source_language in ("hi", "mr") and target_language in ("hi", "mr"):
            english_texts = self.translate_indic_to_en(clean_texts, source_language)
            translated = self.translate_en_to_indic(english_texts, target_language)

        else:
            raise ValueError(
                f"Unsupported translation direction: {source_language} -> {target_language}"
            )

        # Restore original positions and empty values
        result = list(texts)
        for (original_index, _), translated_text in zip(indexed_texts, translated):
            result[original_index] = translated_text

        return result

    # ====================================================
    # ENGLISH -> INDIC
    # ====================================================

    def translate_en_to_indic(
        self,
        texts,
        target_language,
    ):
        if not texts:
            return []

        if target_language not in ("hi", "mr"):
            raise ValueError(f"Unsupported EN -> Indic target: {target_language}")

        self.load_en_indic_model()

        src = LANGUAGE_CODES["en"]
        tgt = LANGUAGE_CODES[target_language]

        tokenizer_inputs = [f"{src} {tgt} {text}" for text in texts]
        print(f"Batch translation: {len(texts)} texts, en -> {target_language}")

        encoded = self.en_indic_tokenizer(
            tokenizer_inputs,
            padding=True,
            truncation=True,
            return_tensors="pt",
        )

        encoded = {key: value.to(self.device) for key, value in encoded.items()}

        with torch.inference_mode():
            generated = self.en_indic_model.generate(
                **encoded,
                max_new_tokens=256,
            )

        results = self.en_indic_tokenizer.batch_decode(
            generated,
            skip_special_tokens=True,
        )

        return [result.strip() for result in results]

    # ====================================================
    # INDIC -> ENGLISH
    # ====================================================

    def translate_indic_to_en(
        self,
        texts,
        source_language,
    ):
        if not texts:
            return []

        if source_language not in ("hi", "mr"):
            raise ValueError(f"Unsupported Indic source: {source_language}")

        self.load_indic_en_model()

        src = LANGUAGE_CODES[source_language]
        tgt = LANGUAGE_CODES["en"]

        tokenizer_inputs = [f"{src} {tgt} {text}" for text in texts]
        print(f"Batch translation: {len(texts)} texts, {source_language} -> en")

        encoded = self.indic_en_tokenizer(
            tokenizer_inputs,
            padding=True,
            truncation=True,
            return_tensors="pt",
        )

        encoded = {key: value.to(self.device) for key, value in encoded.items()}

        with torch.inference_mode():
            generated = self.indic_en_model.generate(
                **encoded,
                max_new_tokens=256,
            )

        results = self.indic_en_tokenizer.batch_decode(
            generated,
            skip_special_tokens=True,
        )

        return [result.strip() for result in results]


translator = Translator()