import pandas as pd

from services.translation_service import translation_service


class CsvHandler:

    def translate(
        self,
        input_file,
        output_file,
        target_language,
    ):

        print(
            "Opening CSV:",
            input_file,
        )

        df = pd.read_csv(
            input_file,
            dtype=object,
            keep_default_na=False,
        )

        # --------------------------------------------------
        # Translate every textual cell
        # --------------------------------------------------

        for column in df.columns:

            for index in df.index:

                value = df.at[
                    index,
                    column,
                ]

                if value is None:
                    continue

                text = str(
                    value
                ).strip()

                if not text:
                    continue

                print(
                    f"Cell [{index}, {column}]: "
                    f"auto -> {target_language}"
                )

                # --------------------------------------------------
                # Do NOT provide source_language.
                #
                # TranslationService will call:
                # detect_language(text)
                # --------------------------------------------------

                translated = (
                    translation_service.translate_text(
                        text=text,
                        target_language=target_language,
                    )
                )

                df.at[
                    index,
                    column
                ] = translated

        # --------------------------------------------------
        # Save translated CSV
        # --------------------------------------------------

        df.to_csv(
            output_file,
            index=False,
            encoding="utf-8-sig",
        )

        print(
            "Translated CSV saved:",
            output_file,
        )


csv_handler = CsvHandler()