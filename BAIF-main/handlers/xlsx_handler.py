import openpyxl
from services.translation_service import translation_service

BATCH_SIZE = 32


class XlsxHandler:
    def translate_xlsx(self, input_path, output_path, target_language="hi", source_language=None):
        wb = openpyxl.load_workbook(input_path)

        for sheet in wb.worksheets:
            cells_to_translate = []

            for row in sheet.iter_rows():
                for cell in row:
                    if cell.value and isinstance(cell.value, str) and cell.value.strip():
                        # Skip formulas
                        if not cell.value.startswith("="):
                            cells_to_translate.append(cell)

            if not cells_to_translate:
                continue

            all_texts = [cell.value for cell in cells_to_translate]
            translated_texts = []

            for i in range(0, len(all_texts), BATCH_SIZE):
                chunk = all_texts[i:i + BATCH_SIZE]
                translated_texts.extend(
                    translation_service.translate_texts(
                        texts=chunk,
                        target_language=target_language,
                        source_language=source_language
                    )
                )

            for cell, trans_text in zip(cells_to_translate, translated_texts):
                cell.value = trans_text

        wb.save(output_path)


xlsx_handler = XlsxHandler()