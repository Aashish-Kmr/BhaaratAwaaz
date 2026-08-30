from docx import Document
from ..services.translation_service import translation_service

BATCH_SIZE = 16


class DocxHandler:
    def translate_docx(self, input_path, output_path, target_language="hi", source_language=None):
        doc = Document(input_path)

        # 1. Collect non-empty paragraphs
        paragraphs_to_translate = [p for p in doc.paragraphs if p.text.strip()]

        # 2. Collect non-empty table cells
        cells_to_translate = []
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        cells_to_translate.append(cell)

        # --------------------------------------------------
        # Batch translate paragraphs
        # --------------------------------------------------
        if paragraphs_to_translate:
            p_texts = [p.text for p in paragraphs_to_translate]
            translated_p_texts = []
            for i in range(0, len(p_texts), BATCH_SIZE):
                chunk = p_texts[i:i + BATCH_SIZE]
                translated_p_texts.extend(
                    translation_service.translate_texts(
                        texts=chunk,
                        target_language=target_language,
                        source_language=source_language
                    )
                )
            for p, trans_text in zip(paragraphs_to_translate, translated_p_texts):
                p.text = trans_text

        # --------------------------------------------------
        # Batch translate table cells
        # --------------------------------------------------
        if cells_to_translate:
            c_texts = [c.text for c in cells_to_translate]
            translated_c_texts = []
            for i in range(0, len(c_texts), BATCH_SIZE):
                chunk = c_texts[i:i + BATCH_SIZE]
                translated_c_texts.extend(
                    translation_service.translate_texts(
                        texts=chunk,
                        target_language=target_language,
                        source_language=source_language
                    )
                )
            for cell, trans_text in zip(cells_to_translate, translated_c_texts):
                cell.text = trans_text

        doc.save(output_path)


docx_handler = DocxHandler()