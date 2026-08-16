import torch

from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
)

from config import (
    EN_INDIC_MODEL_PATH,
    INDIC_EN_MODEL_PATH,
    LANGUAGE_CODES,
)


class Translator:

    def __init__(self):

        print("Creating Translator...")

        self.device = (
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        print("Device:", self.device)

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

        print()
        print("Loading IndicTrans2 EN -> Indic model...")
        print("Path:", EN_INDIC_MODEL_PATH)

        self.en_indic_tokenizer = AutoTokenizer.from_pretrained(
            str(EN_INDIC_MODEL_PATH),
            trust_remote_code=True,
        )

        self.en_indic_model = AutoModelForSeq2SeqLM.from_pretrained(
            str(EN_INDIC_MODEL_PATH),
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

        print()
        print("Loading IndicTrans2 Indic -> EN model...")
        print("Path:", INDIC_EN_MODEL_PATH)

        self.indic_en_tokenizer = AutoTokenizer.from_pretrained(
            str(INDIC_EN_MODEL_PATH),
            trust_remote_code=True,
        )

        self.indic_en_model = AutoModelForSeq2SeqLM.from_pretrained(
            str(INDIC_EN_MODEL_PATH),
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

        # ------------------------------------------------
        # Same language
        # ------------------------------------------------

        if source_language == target_language:
            return text

        # ------------------------------------------------
        # Validate languages
        # ------------------------------------------------

        supported_languages = {"en", "hi", "mr"}

        if source_language not in supported_languages:
            raise ValueError(
                f"Unsupported source language: {source_language}"
            )

        if target_language not in supported_languages:
            raise ValueError(
                f"Unsupported target language: {target_language}"
            )

        # ------------------------------------------------
        # Cache
        # ------------------------------------------------

        key = (
            text,
            source_language,
            target_language,
        )

        if key in self.cache:
            return self.cache[key]

        print(
            f"Translation request: "
            f"{source_language} -> {target_language}"
        )

        # =================================================
        # ENGLISH -> INDIC
        # =================================================

        if source_language == "en":

            result = self.translate_en_to_indic(
                [text],
                target_language,
            )[0]

        # =================================================
        # INDIC -> ENGLISH
        # =================================================

        elif target_language == "en":

            result = self.translate_indic_to_en(
                [text],
                source_language,
            )[0]

        # =================================================
        # HINDI <-> MARATHI
        #
        # IndicTrans2 models available locally are:
        #
        # EN -> Indic
        # Indic -> EN
        #
        # Therefore:
        #
        # Hindi -> Marathi
        # Hindi -> English -> Marathi
        #
        # Marathi -> Hindi
        # Marathi -> English -> Hindi
        # =================================================

        else:

            print(
                f"Using pivot translation: "
                f"{source_language} -> en -> {target_language}"
            )

            # ---------------------------------------------
            # Step 1:
            # Hindi/Marathi -> English
            # ---------------------------------------------

            english_text = self.translate_indic_to_en(
                [text],
                source_language,
            )[0]

            print(
                f"Intermediate English: {english_text}"
            )

            # ---------------------------------------------
            # Step 2:
            # English -> Hindi/Marathi
            # ---------------------------------------------

            result = self.translate_en_to_indic(
                [english_text],
                target_language,
            )[0]

        # ------------------------------------------------
        # Cache result
        # ------------------------------------------------

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

        return [
            self.translate(
                text,
                source_language,
                target_language,
            )
            for text in texts
        ]

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
            raise ValueError(
                f"Unsupported EN -> Indic target: "
                f"{target_language}"
            )

        self.load_en_indic_model()

        src = LANGUAGE_CODES["en"]
        tgt = LANGUAGE_CODES[target_language]

        print(
            f"Source: en -> {src}"
        )

        print(
            f"Target: {target_language} -> {tgt}"
        )

        # ------------------------------------------------
        # IndicTrans2 expects:
        #
        # source_language target_language text
        # ------------------------------------------------

        tokenizer_inputs = [
            f"{src} {tgt} {text}"
            for text in texts
        ]

        print("Input to tokenizer:")

        for item in tokenizer_inputs:
            print(item)

        encoded = self.en_indic_tokenizer(
            tokenizer_inputs,
            padding=True,
            truncation=True,
            return_tensors="pt",
        )

        encoded = {
            key: value.to(self.device)
            for key, value in encoded.items()
        }

        with torch.no_grad():

            generated = self.en_indic_model.generate(
                **encoded,
                max_new_tokens=256,
            )

        results = self.en_indic_tokenizer.batch_decode(
            generated,
            skip_special_tokens=True,
        )

        return [
            result.strip()
            for result in results
        ]

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
            raise ValueError(
                f"Unsupported Indic source: "
                f"{source_language}"
            )

        self.load_indic_en_model()

        src = LANGUAGE_CODES[source_language]
        tgt = LANGUAGE_CODES["en"]

        print(
            f"Source: {source_language} -> {src}"
        )

        print(
            f"Target: en -> {tgt}"
        )

        # ------------------------------------------------
        # IndicTrans2 expects:
        #
        # source_language target_language text
        # ------------------------------------------------

        tokenizer_inputs = [
            f"{src} {tgt} {text}"
            for text in texts
        ]

        print("Input to tokenizer:")

        for item in tokenizer_inputs:
            print(item)

        encoded = self.indic_en_tokenizer(
            tokenizer_inputs,
            padding=True,
            truncation=True,
            return_tensors="pt",
        )

        encoded = {
            key: value.to(self.device)
            for key, value in encoded.items()
        }

        with torch.no_grad():

            generated = self.indic_en_model.generate(
                **encoded,
                max_new_tokens=256,
            )

        results = self.indic_en_tokenizer.batch_decode(
            generated,
            skip_special_tokens=True,
        )

        return [
            result.strip()
            for result in results
        ]


translator = Translator()