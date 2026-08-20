import os
import fitz  # PyMuPDF
from services.translation_service import translation_service

FONT_NAME = "NotoDevanagari"
FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts", "NotoSansDevanagari-Regular.ttf")
BATCH_SIZE = 16


class PdfHandler:
    def __init__(self, font_path=FONT_PATH):
        self.font_path = font_path

    def _register_font(self, page):
        """Registers the Devanagari font if the font file exists."""
        if os.path.exists(self.font_path):
            page.insert_font(fontname=FONT_NAME, fontfile=self.font_path)
            return FONT_NAME
        return "helv"

    def _insert_text_with_fit(self, page, rect, text, fontname, base_fontsize=10, min_fontsize=5, align=fitz.TEXT_ALIGN_LEFT):
        """Fits translated text inside bounding box, stepping down font size if needed."""
        if not text or not text.strip():
            return

        current_fontsize = base_fontsize
        while current_fontsize >= min_fontsize:
            rc = page.insert_textbox(
                rect,
                text,
                fontsize=current_fontsize,
                fontname=fontname,
                align=align
            )
            if rc >= 0:
                return
            current_fontsize -= 0.5

        page.insert_textbox(
            rect,
            text,
            fontsize=min_fontsize,
            fontname=fontname,
            align=align
        )

    def translate_pdf(self, input_pdf_path, output_pdf_path, target_language="hi", source_language=None):
        doc = fitz.open(input_pdf_path)
        output_doc = fitz.open()

        for page_num in range(len(doc)):
            page = doc[page_num]
            rect = page.rect
            
            out_page = output_doc.new_page(width=rect.width, height=rect.height)
            fontname = self._register_font(out_page)

            # --------------------------------------------------
            # 1. Detect Tables & Draw Borders
            # --------------------------------------------------
            tables = page.find_tables()
            table_bboxes = []
            table_cells_to_translate = []

            for tab in tables:
                table_bboxes.append(fitz.Rect(tab.bbox))
                
                # Draw table grid borders
                for r_idx, row in enumerate(tab.rows):
                    for c_idx, cell_bbox in enumerate(row.cells):
                        if cell_bbox is None:
                            continue
                        c_rect = fitz.Rect(cell_bbox)
                        # Draw cell outline
                        out_page.draw_rect(c_rect, color=(0.7, 0.7, 0.7), width=0.5)
                        
                        # Extract cell text
                        cell_text = tab.extract()[r_idx][c_idx]
                        if cell_text and cell_text.strip():
                            table_cells_to_translate.append({
                                "bbox": fitz.Rect(c_rect.x0 + 3, c_rect.y0 + 2, c_rect.x1 - 3, c_rect.y1 - 2),
                                "text": cell_text.strip(),
                                "is_header": (r_idx == 0)
                            })

            # --------------------------------------------------
            # 2. Extract Normal Paragraphs (Excluding Table Areas)
            # --------------------------------------------------
            blocks = page.get_text("blocks")
            normal_blocks = []

            for b in blocks:
                if b[6] == 0:  # Text block
                    block_rect = fitz.Rect(b[0], b[1], b[2], b[3])
                    # Check if block overlaps with any detected table
                    is_inside_table = any(block_rect.intersects(tb) for tb in table_bboxes)
                    if not is_inside_table:
                        raw_text = b[4].strip()
                        if raw_text:
                            normal_blocks.append({
                                "bbox": block_rect,
                                "text": raw_text
                            })

            # --------------------------------------------------
            # 3. Batch Translate All Text Items Together
            # --------------------------------------------------
            all_items = normal_blocks + table_cells_to_translate
            if not all_items:
                continue

            all_texts = [item["text"] for item in all_items]
            translated_texts = []

            for i in range(0, len(all_texts), BATCH_SIZE):
                chunk = all_texts[i:i + BATCH_SIZE]
                translated_chunk = translation_service.translate_texts(
                    texts=chunk,
                    target_language=target_language,
                    source_language=source_language
                )
                translated_texts.extend(translated_chunk)

            # --------------------------------------------------
            # 4. Render Translated Elements
            # --------------------------------------------------
            for item, trans_text in zip(all_items, translated_texts):
                base_font = 9 if item.get("is_header") or "is_header" in item else 10
                self._insert_text_with_fit(
                    page=out_page,
                    rect=item["bbox"],
                    text=trans_text,
                    fontname=fontname,
                    base_fontsize=base_font
                )

        output_doc.save(output_pdf_path)
        output_doc.close()
        doc.close()


pdf_handler = PdfHandler()