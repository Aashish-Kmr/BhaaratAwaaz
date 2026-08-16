from translator import translator
from utils.language import detect_language


class TranslationService:

    def translate_text(
        self,
        text,
        target_language,
        source_language=None,
    ):

        if not text or not text.strip():
            return text

        # Detect source language if not provided
        if source_language is None:
            source_language = detect_language(text)

        print(
            f"Translation request: "
            f"{source_language} -> {target_language}"
        )

        # Same language
        if source_language == target_language:
            return text

        return translator.translate(
            text=text,
            source_language=source_language,
            target_language=target_language,
        )


translation_service = TranslationService()