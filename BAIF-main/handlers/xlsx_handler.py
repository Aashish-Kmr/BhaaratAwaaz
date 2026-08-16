from openpyxl import load_workbook

from services.translation_service import translation_service
from utils.language import detect_language


class XlsxHandler:

    def translate(
        self,
        input_file,
        output_file,
        target_language,
    ):
        print("Opening XLSX:", input_file)

        workbook = load_workbook(
            input_file,
            data_only=False,
        )

        for worksheet in workbook.worksheets:

            print(
                f"Processing worksheet: {worksheet.title}"
            )

            for row in worksheet.iter_rows():

                for cell in row:

                    value = cell.value

                    # --------------------------------------------
                    # Skip empty cells
                    # --------------------------------------------

                    if value is None:
                        continue

                    # --------------------------------------------
                    # Skip formulas
                    # --------------------------------------------

                    if isinstance(value, str) and value.startswith("="):
                        continue

                    # --------------------------------------------
                    # Translate only string values
                    # --------------------------------------------

                    if not isinstance(value, str):
                        continue

                    text = value.strip()

                    if not text:
                        continue

                    # --------------------------------------------
                    # Detect source language
                    # --------------------------------------------

                    source_language = detect_language(text)

                    print(
                        f"Cell {cell.coordinate}: "
                        f"{source_language} -> {target_language}"
                    )

                    # --------------------------------------------
                    # Same language
                    # --------------------------------------------

                    if source_language == target_language:
                        continue

                    # --------------------------------------------
                    # Translate
                    # --------------------------------------------

                    translated = translation_service.translate_text(
                        text=text,
                        target_language=target_language,
                        source_language=source_language,
                    )

                    # --------------------------------------------
                    # Replace ONLY cell value
                    #
                    # Existing formatting is preserved.
                    # --------------------------------------------

                    cell.value = translated

        # --------------------------------------------
        # Save workbook
        # --------------------------------------------

        workbook.save(output_file)

        print(
            "Translated XLSX saved:",
            output_file,
        )


xlsx_handler = XlsxHandler()