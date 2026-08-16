from __future__ import annotations

from typing import Callable

import pandas as pd

from app.core.translation import translator


class CsvHandler:
    def translate(
        self,
        input_file,
        output_file,
        source_language: str,
        target_language: str,
        on_progress: Callable[[float], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ):
        df = pd.read_csv(input_file, dtype=object, keep_default_na=False)

        cells = [(index, column) for column in df.columns for index in df.index]
        total = max(1, len(cells))

        for progress_index, (index, column) in enumerate(cells):
            if should_stop and should_stop():
                break

            value = df.at[index, column]

            if value is not None:
                text = str(value).strip()
                if text:
                    df.at[index, column] = translator.translate(
                        text, source_language, target_language
                    )

            if on_progress:
                on_progress((progress_index + 1) / total)

        df.to_csv(output_file, index=False, encoding="utf-8-sig")


csv_handler = CsvHandler()
