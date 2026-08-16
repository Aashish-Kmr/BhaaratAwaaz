from __future__ import annotations

from typing import Callable

import pymupdf as fitz

from app import config
from app.core.translation import translator


class PdfHandler:
    def __init__(self):
        self.font_path = str(config.DEVANAGARI_FONT_PATH)

        if not config.DEVANAGARI_FONT_PATH.exists():
            raise FileNotFoundError(f"Devanagari font not found: {self.font_path}")

    def translate(
        self,
        input_file,
        output_file,
        source_language: str,
        target_language: str,
        on_progress: Callable[[float], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ):
        source_document = fitz.open(input_file)
        output_document = fitz.open()

        try:
            total_pages = max(1, len(source_document))

            for page_number, source_page in enumerate(source_document):
                if should_stop and should_stop():
                    break

                output_page = output_document.new_page(
                    width=source_page.rect.width,
                    height=source_page.rect.height,
                )

                output_page.insert_font(fontname="NotoDevanagari", fontfile=self.font_path)

                table_rects = []

                try:
                    tables = source_page.find_tables()
                    for table in tables.tables:
                        table_rect = fitz.Rect(table.bbox)
                        table_rects.append(table_rect)
                        self._translate_table(
                            source_page=source_page,
                            output_page=output_page,
                            table=table,
                            source_language=source_language,
                            target_language=target_language,
                        )
                except Exception:
                    table_rects = []

                self._translate_page_text(
                    source_page=source_page,
                    output_page=output_page,
                    source_language=source_language,
                    target_language=target_language,
                    table_rects=table_rects,
                )

                if on_progress:
                    on_progress((page_number + 1) / total_pages)

            output_document.save(output_file, garbage=4, deflate=True)
        finally:
            output_document.close()
            source_document.close()

    def _translate_page_text(
        self, source_page, output_page, source_language, target_language, table_rects
    ):
        blocks = source_page.get_text("dict").get("blocks", [])

        paragraph_blocks = []

        for block in blocks:
            if block.get("type") != 0:
                continue

            block_rect = fitz.Rect(block["bbox"])

            if self._rect_intersects_table(block_rect, table_rects):
                continue

            text_parts = []
            font_size = 11

            for line in block.get("lines", []):
                line_text = ""
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text:
                        continue
                    line_text += text
                    font_size = max(font_size, span.get("size", 11))

                if line_text.strip():
                    text_parts.append(line_text.strip())

            if not text_parts:
                continue

            block_text = "\n".join(text_parts).strip()
            if not block_text:
                continue

            paragraph_blocks.append(
                {"rect": block_rect, "text": block_text, "font_size": font_size}
            )

        paragraphs = self._group_adjacent_blocks(paragraph_blocks)

        for paragraph in paragraphs:
            translated = translator.translate(
                paragraph["text"], source_language, target_language
            )

            if not translated:
                continue

            self._insert_text_in_rect(
                output_page=output_page,
                rect=paragraph["rect"],
                text=translated,
                font_size=paragraph["font_size"],
            )

    def _translate_table(
        self, source_page, output_page, table, source_language, target_language
    ):
        table_bbox = fitz.Rect(table.bbox)
        rows = getattr(table, "rows", [])

        if not rows:
            return

        output_page.draw_rect(table_bbox, color=(0, 0, 0), width=0.7)

        for row in rows:
            cells = getattr(row, "cells", [])
            if not cells:
                continue

            for cell in cells:
                if cell is None:
                    continue

                cell_rect = fitz.Rect(cell)
                output_page.draw_rect(cell_rect, color=(0, 0, 0), width=0.5)

                cell_text = self._extract_text_from_rect(source_page, cell_rect)
                if not cell_text.strip():
                    continue

                translated = translator.translate(cell_text, source_language, target_language)
                if not translated:
                    continue

                text_rect = fitz.Rect(
                    cell_rect.x0 + 3, cell_rect.y0 + 2, cell_rect.x1 - 3, cell_rect.y1 - 2
                )

                font_size = self._get_font_size_from_rect(source_page, cell_rect)

                self._insert_text_in_rect(
                    output_page=output_page,
                    rect=text_rect,
                    text=translated,
                    font_size=font_size,
                    align=0,
                )

    def _extract_text_from_rect(self, page, rect):
        text = page.get_text("text", clip=rect)
        return text.strip() if text else ""

    def _get_font_size_from_rect(self, page, rect):
        try:
            data = page.get_text("dict", clip=rect)
            sizes = []

            for block in data.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        size = span.get("size")
                        if size:
                            sizes.append(size)

            if sizes:
                return max(7, min(max(sizes), 18))
        except Exception:
            pass

        return 10

    def _group_adjacent_blocks(self, blocks):
        if not blocks:
            return []

        blocks = sorted(blocks, key=lambda item: (item["rect"].y0, item["rect"].x0))

        paragraphs = []
        current = None

        for block in blocks:
            rect = block["rect"]

            if current is None:
                current = {
                    "rect": fitz.Rect(rect),
                    "text": block["text"],
                    "font_size": block["font_size"],
                }
                continue

            current_rect = current["rect"]
            vertical_gap = rect.y0 - current_rect.y1
            overlap = self._horizontal_overlap(current_rect, rect)

            same_paragraph = vertical_gap <= max(12, current["font_size"] * 0.9) and overlap > 0

            if same_paragraph:
                current["text"] += " " + block["text"]
                current["rect"] = self._union_rects(current["rect"], rect)
                current["font_size"] = max(current["font_size"], block["font_size"])
            else:
                paragraphs.append(current)
                current = {
                    "rect": fitz.Rect(rect),
                    "text": block["text"],
                    "font_size": block["font_size"],
                }

        if current is not None:
            paragraphs.append(current)

        return paragraphs

    def _horizontal_overlap(self, rect1, rect2):
        left = max(rect1.x0, rect2.x0)
        right = min(rect1.x1, rect2.x1)
        return max(0, right - left)

    def _union_rects(self, rect1, rect2):
        # Installed PyMuPDF's Rect has no .union(), so this is done manually.
        return fitz.Rect(
            min(rect1.x0, rect2.x0),
            min(rect1.y0, rect2.y0),
            max(rect1.x1, rect2.x1),
            max(rect1.y1, rect2.y1),
        )

    def _rect_intersects_table(self, rect, table_rects):
        for table_rect in table_rects:
            x_overlap = min(rect.x1, table_rect.x1) - max(rect.x0, table_rect.x0)
            y_overlap = min(rect.y1, table_rect.y1) - max(rect.y0, table_rect.y0)
            if x_overlap > 0 and y_overlap > 0:
                return True
        return False

    def _insert_text_in_rect(self, output_page, rect, text, font_size, align=0):
        font_size = max(7, min(font_size, 18))

        while font_size >= 7:
            result = output_page.insert_textbox(
                rect,
                text,
                fontsize=font_size,
                fontname="NotoDevanagari",
                align=align,
                lineheight=1.15,
            )

            if result >= 0:
                return

            font_size -= 0.5

        output_page.insert_textbox(
            rect, text, fontsize=7, fontname="NotoDevanagari", align=align, lineheight=1.15
        )


pdf_handler = PdfHandler()
