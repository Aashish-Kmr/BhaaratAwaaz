# from typing import List
# import os

# import torch
# from transformers import (
#     AutoTokenizer,
#     AutoModelForSeq2SeqLM,
# )

# from app.config import INDIC_LANG_CODES


# class Translator:

#     # ---------------------------------------------------------
#     # Models
#     # ---------------------------------------------------------

#     # Already working for Marathi <-> Hindi
#     INDIC_INDIC_MODEL = (
#         "ai4bharat/indictrans2-indic-indic-dist-320M"
#     )

#     # Non-gated multilingual fallback for ANY direction
#     # involving English.
#     NLLB_MODEL = (
#         "facebook/nllb-200-distilled-600M"
#     )

#     # ---------------------------------------------------------
#     # Constructor
#     # ---------------------------------------------------------

#     def __init__(self):

#         self.device = "cpu"

#         cpu_threads = max(
#             1,
#             (os.cpu_count() or 4) - 1,
#         )

#         torch.set_num_threads(cpu_threads)
#         torch.set_num_interop_threads(1)

#         print(
#             f"Using {cpu_threads} CPU threads for translation"
#         )

#         # Lazy-loaded:
#         # model name -> (tokenizer, model)
#         self._models = {}

#     # ---------------------------------------------------------
#     # Language mapping
#     # ---------------------------------------------------------

#     def _get_language_code(
#         self,
#         language: str,
#     ) -> str:

#         normalized = (
#             language
#             .strip()
#             .lower()
#         )

#         aliases = {
#             "marathi": "mar_Deva",
#             "mr": "mar_Deva",
#             "mar": "mar_Deva",

#             "hindi": "hin_Deva",
#             "hi": "hin_Deva",
#             "hin": "hin_Deva",

#             "english": "eng_Latn",
#             "en": "eng_Latn",
#             "eng": "eng_Latn",
#         }

#         if normalized in aliases:
#             return aliases[normalized]

#         # Also support our config.py mapping
#         if normalized in INDIC_LANG_CODES:
#             return INDIC_LANG_CODES[normalized]

#         if "_" in language:
#             return language

#         raise ValueError(
#             f"Unsupported language: {language}. "
#             "Supported languages: Marathi, Hindi, English."
#         )

#     # ---------------------------------------------------------
#     # Model selection
#     # ---------------------------------------------------------

#     def _select_model(
#         self,
#         source_code: str,
#         target_code: str,
#     ) -> str:

#         return self.NLLB_MODEL

#     # ---------------------------------------------------------
#     # Load model lazily
#     # ---------------------------------------------------------

#     def _load_model(
#         self,
#         model_name: str,
#     ):

#         if model_name in self._models:
#             return self._models[model_name]

#         print()
#         print("=" * 60)
#         print("Loading translation model:")
#         print(model_name)
#         print("=" * 60)

#         tokenizer = AutoTokenizer.from_pretrained(
#             model_name,
#             trust_remote_code=True,
#         )

#         model = (
#             AutoModelForSeq2SeqLM
#             .from_pretrained(
#                 model_name,
#                 trust_remote_code=True,
#             )
#             .to(self.device)
#         )

#         model.eval()

#         self._models[model_name] = (
#             tokenizer,
#             model,
#         )

#         print(
#             f"Translation model ready: {model_name}"
#         )

#         return (
#             tokenizer,
#             model,
#         )

#     # ---------------------------------------------------------
#     # IndicTrans2 translation
#     # ---------------------------------------------------------

#     def _translate_indictrans2(
#         self,
#         texts: List[str],
#         source_code: str,
#         target_code: str,
#     ) -> List[str]:

#         tokenizer, model = self._load_model(
#             self.INDIC_INDIC_MODEL
#         )

#         prepared = [
#             (
#                 f"{source_code} "
#                 f"{target_code} "
#                 f"{text.strip()}"
#             )
#             for text in texts
#         ]

#         print(
#             f"[IndicTrans2] "
#             f"{source_code} -> {target_code}"
#         )

#         inputs = tokenizer(
#             prepared,
#             padding="longest",
#             truncation=True,
#             max_length=256,
#             return_tensors="pt",
#             return_attention_mask=True,
#         )

#         inputs = {
#             key: value.to(self.device)
#             for key, value in inputs.items()
#         }

#         with torch.inference_mode():

#             outputs = model.generate(
#                 **inputs,
#                 use_cache=False,
#                 max_length=128,
#                 num_beams=1,
#                 num_return_sequences=1,
#             )

#         translations = tokenizer.batch_decode(
#             outputs.detach().cpu(),
#             skip_special_tokens=True,
#             clean_up_tokenization_spaces=True,
#         )

#         return [
#             text.strip()
#             for text in translations
#         ]

#     # ---------------------------------------------------------
#     # NLLB translation
#     # ---------------------------------------------------------

#     def _translate_nllb(
#         self,
#         texts: List[str],
#         source_code: str,
#         target_code: str,
#     ) -> List[str]:

#         tokenizer, model = self._load_model(
#             self.NLLB_MODEL
#         )

#         print(
#             f"[NLLB] "
#             f"{source_code} -> {target_code}"
#         )

#         # NLLB uses src_lang on the tokenizer.
#         tokenizer.src_lang = source_code

#         inputs = tokenizer(
#             texts,
#             padding=True,
#             truncation=True,
#             max_length=256,
#             return_tensors="pt",
#         )

#         inputs = {
#             key: value.to(self.device)
#             for key, value in inputs.items()
#         }

#         target_token_id = (
#             tokenizer.convert_tokens_to_ids(
#                 target_code
#             )
#         )

#         with torch.inference_mode():

#             outputs = model.generate(
#                 **inputs,
#                 forced_bos_token_id=target_token_id,
#                 max_length=128,
#                 num_beams=1,
#                 use_cache=True,
#             )

#         translations = tokenizer.batch_decode(
#             outputs.detach().cpu(),
#             skip_special_tokens=True,
#             clean_up_tokenization_spaces=True,
#         )

#         return [
#             text.strip()
#             for text in translations
#         ]

#     # ---------------------------------------------------------
#     # Public batch translation
#     # ---------------------------------------------------------

#     def translate_batch(
#         self,
#         texts: List[str],
#         source_language: str,
#         target_language: str,
#     ) -> List[str]:

#         if not texts:
#             return []

#         source_code = self._get_language_code(
#             source_language
#         )

#         target_code = self._get_language_code(
#             target_language
#         )

#         print()
#         print("=" * 60)
#         print("TRANSLATION")
#         print(f"Source : {source_language}")
#         print(f"Target : {target_language}")
#         print(f"Source : {source_code}")
#         print(f"Target : {target_code}")
#         print("=" * 60)

#         # Same-language request
#         if source_code == target_code:

#             print(
#                 "Source and target identical - "
#                 "skipping translation."
#             )

#             return texts

#         model_name = self._select_model(
#             source_code,
#             target_code,
#         )

#         print(
#             f"Selected model: {model_name}"
#         )

#         # Marathi <-> Hindi
#         if model_name == self.INDIC_INDIC_MODEL:

#             translations = (
#                 self._translate_indictrans2(
#                     texts,
#                     source_code,
#                     target_code,
#                 )
#             )

#         # Any direction involving English
#         else:

#             translations = (
#                 self._translate_nllb(
#                     texts,
#                     source_code,
#                     target_code,
#                 )
#             )

#         print(
#             f"Generated {len(translations)} translations"
#         )

#         for index, text in enumerate(
#             translations[:3],
#             start=1,
#         ):

#             print(
#                 f"[{index}] {text}"
#             )

#         return translations

#     # ---------------------------------------------------------
#     # Segment translation
#     # ---------------------------------------------------------

#     def translate_segments(
#         self,
#         segments: list[dict],
#         source_language: str,
#         target_language: str,
#         batch_size: int = 32,
#     ) -> list[dict]:

#         if not segments:
#             return []

#         source_code = self._get_language_code(
#             source_language
#         )

#         target_code = self._get_language_code(
#             target_language
#         )

#         if source_code == target_code:
#             return segments

#         translated_segments = []

#         for start in range(
#             0,
#             len(segments),
#             batch_size,
#         ):

#             chunk = segments[
#                 start:start + batch_size
#             ]

#             texts = [
#                 segment.get(
#                     "text",
#                     "",
#                 ).strip()
#                 for segment in chunk
#             ]

#             valid_indices = [
#                 i
#                 for i, text in enumerate(texts)
#                 if text
#             ]

#             if not valid_indices:
#                 translated_segments.extend(chunk)
#                 continue

#             valid_texts = [
#                 texts[i]
#                 for i in valid_indices
#             ]

#             translations = self.translate_batch(
#                 valid_texts,
#                 source_language,
#                 target_language,
#             )

#             translation_map = dict(
#                 zip(
#                     valid_indices,
#                     translations,
#                 )
#             )

#             for i, segment in enumerate(chunk):

#                 translated_text = (
#                     translation_map.get(
#                         i,
#                         segment.get(
#                             "text",
#                             "",
#                         ),
#                     )
#                 )

#                 translated_segments.append(
#                     {
#                         **segment,
#                         "text": translated_text.strip(),
#                     }
#                 )

#         return translated_segments


































from typing import List
import os

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
)

from ..config import INDIC_LANG_CODES


class Translator:

    NLLB_MODEL = (
        "facebook/nllb-200-distilled-600M"
    )

    def __init__(self):

        self.device = "cpu"

        cpu_threads = max(
            1,
            (os.cpu_count() or 4) - 1,
        )

        torch.set_num_threads(cpu_threads)
        torch.set_num_interop_threads(1)

        print(
            f"Using {cpu_threads} CPU threads "
            f"for translation"
        )

        self._models = {}

    def _get_language_code(
        self,
        language: str,
    ) -> str:

        normalized = language.strip().lower()

        aliases = {
            "marathi": "mar_Deva",
            "mr": "mar_Deva",
            "mar": "mar_Deva",

            "hindi": "hin_Deva",
            "hi": "hin_Deva",
            "hin": "hin_Deva",

            "english": "eng_Latn",
            "en": "eng_Latn",
            "eng": "eng_Latn",
        }

        if normalized in aliases:
            return aliases[normalized]

        if normalized in INDIC_LANG_CODES:
            return INDIC_LANG_CODES[normalized]

        if "_" in language:
            return language

        raise ValueError(
            f"Unsupported language: {language}"
        )

    def _load_model(self):

        if self.NLLB_MODEL in self._models:
            return self._models[self.NLLB_MODEL]

        print()
        print("=" * 60)
        print("Loading NLLB")
        print("=" * 60)

        tokenizer = AutoTokenizer.from_pretrained(
            self.NLLB_MODEL
        )

        model = (
            AutoModelForSeq2SeqLM
            .from_pretrained(
                self.NLLB_MODEL
            )
            .to(self.device)
        )

        # CPU dynamic INT8 quantization.
        print("Applying CPU INT8 quantization...")

        model = torch.quantization.quantize_dynamic(
            model,
            {
                torch.nn.Linear
            },
            dtype=torch.qint8,
        )

        model.eval()

        self._models[self.NLLB_MODEL] = (
            tokenizer,
            model,
        )

        print("NLLB ready.")

        return (
            tokenizer,
            model,
        )

    def translate_batch(
        self,
        texts: List[str],
        source_language: str,
        target_language: str,
    ) -> List[str]:

        if not texts:
            return []

        source_code = self._get_language_code(
            source_language
        )

        target_code = self._get_language_code(
            target_language
        )

        print()
        print("=" * 60)
        print("TRANSLATION")
        print(
            f"Source : {source_language}"
        )
        print(
            f"Target : {target_language}"
        )
        print(
            f"Codes  : "
            f"{source_code} -> {target_code}"
        )
        print("=" * 60)

        if source_code == target_code:
            return texts

        tokenizer, model = self._load_model()

        tokenizer.src_lang = source_code

        inputs = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors="pt",
        )

        inputs = {
            key: value.to(self.device)
            for key, value in inputs.items()
        }

        target_token_id = (
            tokenizer.convert_tokens_to_ids(
                target_code
            )
        )

        with torch.inference_mode():

            outputs = model.generate(
                **inputs,
                forced_bos_token_id=target_token_id,

                # This was greedy (num_beams=1) with no repetition guards,
                # which is the textbook recipe for NMT degeneration: a
                # clean Marathi segment could come back as
                # "और उसके बाल और उसके बाल और उसके बाल ..." repeated until
                # max_length.
                #
                # Measured on exactly that failing segment: greedy took
                # 35.0s and looped; the settings below took 16.8s and came
                # back clean. It is *faster* despite beam search, because a
                # degenerate decode always runs to the full 128 tokens
                # while a good one stops early.
                num_beams=4,
                early_stopping=True,
                do_sample=False,

                # Forbid any 3-gram from repeating, and mildly penalise
                # repeated tokens.
                no_repeat_ngram_size=3,
                repetition_penalty=1.1,

                max_length=128,
                use_cache=True,
            )

        translations = tokenizer.batch_decode(
            outputs.detach().cpu(),
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )

        return [
            text.strip()
            for text in translations
        ]

    # Sentence terminators seen in Devanagari and Latin transcripts.
    _SENTENCE_ENDS = "।॥.?!"

    @classmethod
    def _split_sentences(cls, text: str) -> list[str]:
        """
        Break a segment into sentences.

        NLLB is a sentence-level model. ASR segments here can run to 60
        seconds and carry four or more sentences, which is well outside
        what it was trained on and is precisely when it degenerates into a
        repetition loop. Splitting first was worth more than any decoding
        flag: on the observed failing segment, greedy decoding on the whole
        chunk looped, while the same decoding per sentence did not.
        """

        sentences = []
        current = ""

        for character in text:
            current += character
            if character in cls._SENTENCE_ENDS:
                if current.strip():
                    sentences.append(current.strip())
                current = ""

        if current.strip():
            sentences.append(current.strip())

        return sentences or [text]

    def translate_segments(
        self,
        segments: list[dict],
        source_language: str,
        target_language: str,
        batch_size: int = 64,
    ) -> list[dict]:

        if not segments:
            return []

        source_code = self._get_language_code(
            source_language
        )

        target_code = self._get_language_code(
            target_language
        )

        if source_code == target_code:
            return segments

        translated_segments = []

        for start in range(
            0,
            len(segments),
            batch_size,
        ):

            chunk = segments[
                start:start + batch_size
            ]

            texts = [
                segment.get(
                    "text",
                    "",
                ).strip()
                for segment in chunk
            ]

            valid_indices = [
                i
                for i, text in enumerate(texts)
                if text
            ]

            if not valid_indices:
                translated_segments.extend(chunk)
                continue

            # Translate per sentence rather than per segment (see
            # _split_sentences), then stitch each segment back together.
            # All sentences in this chunk still go through the model as one
            # batch, so this does not cost an extra pass.
            sentences = []
            spans = []

            for i in valid_indices:
                parts = self._split_sentences(texts[i])
                spans.append((i, len(sentences), len(parts)))
                sentences.extend(parts)

            translated_sentences = self.translate_batch(
                sentences,
                source_language,
                target_language,
            )

            translation_map = {
                i: " ".join(
                    translated_sentences[offset:offset + count]
                ).strip()
                for i, offset, count in spans
            }

            for i, segment in enumerate(chunk):

                translated_text = (
                    translation_map.get(
                        i,
                        segment.get(
                            "text",
                            "",
                        ),
                    )
                )

                translated_segments.append(
                    {
                        **segment,
                        "text": translated_text.strip(),
                    }
                )

        return translated_segments