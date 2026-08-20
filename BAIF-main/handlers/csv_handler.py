import csv
from services.translation_service import translation_service

BATCH_SIZE = 32


class CsvHandler:
    def translate_csv(self, input_path, output_path, target_language="hi", source_language=None, encoding="utf-8"):
        with open(input_path, mode="r", encoding=encoding, errors="ignore") as f:
            reader = list(csv.reader(f))

        if not reader:
            with open(output_path, mode="w", encoding="utf-8-sig", newline="") as f:
                pass
            return

        cell_coords = []
        texts_to_translate = []

        for r_idx, row in enumerate(reader):
            for c_idx, val in enumerate(row):
                if val.strip():
                    cell_coords.append((r_idx, c_idx))
                    texts_to_translate.append(val)

        if not texts_to_translate:
            with open(output_path, mode="w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(reader)
            return

        translated_texts = []
        for i in range(0, len(texts_to_translate), BATCH_SIZE):
            chunk = texts_to_translate[i:i + BATCH_SIZE]
            translated_texts.extend(
                translation_service.translate_texts(
                    texts=chunk,
                    target_language=target_language,
                    source_language=source_language
                )
            )

        for (r_idx, c_idx), trans_text in zip(cell_coords, translated_texts):
            reader[r_idx][c_idx] = trans_text

        with open(output_path, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(reader)


csv_handler = CsvHandler()