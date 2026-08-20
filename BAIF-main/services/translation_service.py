from translator import translator
from utils.language import detect_language


class TranslationService:

    def translate_text(
        self,
        text,
        target_language,
        source_language=None,
    ):
        """
        Translate a single text.

        This method is kept for backward compatibility with the
        existing DOCX, XLSX, PPTX and CSV handlers.
        """

        if not text or not str(text).strip():
            return text

        text = str(text)

        target_language = target_language.lower()

        # Detect source language if not provided
        if source_language is None:
            source_language = detect_language(text)

        source_language = source_language.lower()

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

    def translate_texts(
        self,
        texts,
        target_language,
        source_language=None,
    ):
        """
        Translate multiple texts using a single model batch.

        Parameters
        ----------
        texts : list
            List of strings to translate.

        target_language : str
            Target language code:
                en
                hi
                mr

        source_language : str, optional
            Source language code.

            If None, language is detected for each text.

        Returns
        -------
        list
            Translated texts in the same order as the input.

        Notes
        -----
        Empty strings are preserved.
        Input ordering is preserved.
        """

        if not texts:
            return []

        target_language = target_language.lower()

        # --------------------------------------------------
        # Preserve original input exactly
        # --------------------------------------------------

        original_texts = list(texts)

        # --------------------------------------------------
        # Build list of non-empty texts
        #
        # We keep their original indexes so the translated
        # results can be mapped back to the correct position.
        # --------------------------------------------------

        indexed_texts = []

        for index, text in enumerate(original_texts):

            if text is None:
                continue

            text = str(text)

            if not text.strip():
                continue

            indexed_texts.append(
                (
                    index,
                    text,
                )
            )

        # Nothing to translate
        if not indexed_texts:
            return original_texts

        # --------------------------------------------------
        # If source language was explicitly supplied,
        # everything can go through one model batch.
        # --------------------------------------------------

        if source_language is not None:

            source_language = source_language.lower()

            clean_texts = [
                text
                for _, text in indexed_texts
            ]

            print(
                f"Batch translation request: "
                f"{len(clean_texts)} texts, "
                f"{source_language} -> "
                f"{target_language}"
            )

            # Same language - no model inference
            if source_language == target_language:

                return original_texts

            translated = translator.translate_batch(
                texts=clean_texts,
                source_language=source_language,
                target_language=target_language,
            )

            result = list(original_texts)

            for (
                (original_index, _),
                translated_text,
            ) in zip(
                indexed_texts,
                translated,
            ):
                result[original_index] = translated_text

            return result

        # --------------------------------------------------
        # Automatic language detection
        #
        # Different source languages cannot safely be sent
        # through the same model batch because the tokenizer
        # requires the correct source language.
        #
        # Therefore group texts by detected language.
        # --------------------------------------------------

        language_groups = {}

        for original_index, text in indexed_texts:

            detected_language = detect_language(text)

            detected_language = detected_language.lower()

            if detected_language not in language_groups:
                language_groups[detected_language] = []

            language_groups[detected_language].append(
                (
                    original_index,
                    text,
                )
            )

        result = list(original_texts)

        # --------------------------------------------------
        # Translate each language group as one batch
        # --------------------------------------------------

        for (
            detected_language,
            group,
        ) in language_groups.items():

            group_texts = [
                text
                for _, text in group
            ]

            print(
                f"Batch translation request: "
                f"{len(group_texts)} texts, "
                f"{detected_language} -> "
                f"{target_language}"
            )

            # Same language
            if detected_language == target_language:

                translated = group_texts

            else:

                translated = translator.translate_batch(
                    texts=group_texts,
                    source_language=detected_language,
                    target_language=target_language,
                )

            # --------------------------------------------------
            # Restore results to their original positions
            # --------------------------------------------------

            for (
                (original_index, _),
                translated_text,
            ) in zip(
                group,
                translated,
            ):
                result[original_index] = translated_text

        return result


translation_service = TranslationService()