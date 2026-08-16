import os
import fitz

from services.translation_service import translation_service


class PdfHandler:

    def __init__(self):

        # --------------------------------------------------
        # Font
        # --------------------------------------------------

        # BAIF/fonts/NotoSansDevanagari-Regular.ttf
        base_dir = os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )

        self.font_path = os.path.join(
            base_dir,
            "fonts",
            "NotoSansDevanagari-Regular.ttf",
        )

        print(
            "PDF font path:",
            self.font_path,
        )

        if not os.path.exists(
            self.font_path
        ):
            raise FileNotFoundError(
                "Devanagari font not found: "
                f"{self.font_path}"
            )

    # ======================================================
    # TRANSLATE
    # ======================================================

    def translate(
        self,
        input_file,
        output_file,
        target_language,
        source_language=None,
    ):

        print(
            "Opening PDF:",
            input_file,
        )

        source_document = fitz.open(
            input_file
        )

        output_document = fitz.open()

        try:

            total_pages = len(
                source_document
            )

            # --------------------------------------------------
            # Process each page independently.
            #
            # This is important because paragraphs/tables
            # must never cross page boundaries.
            # --------------------------------------------------

            for page_number, source_page in enumerate(
                source_document
            ):

                print(
                    f"Processing page "
                    f"{page_number + 1}/"
                    f"{total_pages}"
                )

                # ----------------------------------------------
                # Preserve original page dimensions
                # ----------------------------------------------

                output_page = (
                    output_document.new_page(
                        width=source_page.rect.width,
                        height=source_page.rect.height,
                    )
                )

                # ----------------------------------------------
                # Register Devanagari font once for this page
                # ----------------------------------------------

                output_page.insert_font(
                    fontname="NotoDevanagari",
                    fontfile=self.font_path,
                )

                # ----------------------------------------------
                # Detect tables first
                # ----------------------------------------------

                table_rects = []

                try:

                    tables = source_page.find_tables()

                    print(
                        "Tables detected:",
                        len(tables.tables),
                    )

                    for table_index, table in enumerate(
                        tables.tables
                    ):

                        table_rect = fitz.Rect(
                            table.bbox
                        )

                        table_rects.append(
                            table_rect
                        )

                        print(
                            f"  Table "
                            f"{table_index + 1}: "
                            f"{table_rect}"
                        )

                        self._translate_table(
                            source_page=source_page,
                            output_page=output_page,
                            table=table,
                            target_language=target_language,
                            source_language=source_language,
                        )

                except Exception as exc:

                    # ------------------------------------------
                    # Table detection should not make the
                    # entire PDF translation fail.
                    # ------------------------------------------

                    print(
                        "Table detection warning:",
                        repr(exc),
                    )

                    table_rects = []

                # ----------------------------------------------
                # Process normal text blocks.
                #
                # Text inside detected tables is skipped so
                # that table cells are NOT translated twice.
                # ----------------------------------------------

                self._translate_page_text(
                    source_page=source_page,
                    output_page=output_page,
                    target_language=target_language,
                    source_language=source_language,
                    table_rects=table_rects,
                )

                print(
                    f"Page "
                    f"{page_number + 1} completed."
                )

            # --------------------------------------------------
            # Save final PDF
            # --------------------------------------------------

            output_document.save(
                output_file,
                garbage=4,
                deflate=True,
            )

            print(
                "Translated PDF saved:",
                output_file,
            )

        finally:

            output_document.close()
            source_document.close()

    # ======================================================
    # NORMAL PAGE TEXT
    # ======================================================

    def _translate_page_text(
        self,
        source_page,
        output_page,
        target_language,
        source_language,
        table_rects,
    ):

        blocks = source_page.get_text(
            "dict"
        ).get(
            "blocks",
            []
        )

        # --------------------------------------------------
        # Convert text blocks into paragraph candidates
        # --------------------------------------------------

        paragraph_blocks = []

        for block in blocks:

            # Ignore images/non-text blocks
            if block.get("type") != 0:
                continue

            block_rect = fitz.Rect(
                block["bbox"]
            )

            # ----------------------------------------------
            # Skip blocks belonging to tables.
            # ----------------------------------------------

            if self._rect_intersects_table(
                block_rect,
                table_rects,
            ):
                continue

            text_parts = []

            font_size = 11

            for line in block.get(
                "lines",
                [],
            ):

                line_text = ""

                for span in line.get(
                    "spans",
                    [],
                ):

                    text = span.get(
                        "text",
                        "",
                    )

                    if not text:
                        continue

                    line_text += text

                    font_size = max(
                        font_size,
                        span.get(
                            "size",
                            11,
                        ),
                    )

                if line_text.strip():

                    text_parts.append(
                        line_text.strip()
                    )

            if not text_parts:
                continue

            block_text = "\n".join(
                text_parts
            ).strip()

            if not block_text:
                continue

            paragraph_blocks.append(
                {
                    "rect": block_rect,
                    "text": block_text,
                    "font_size": font_size,
                }
            )

        # --------------------------------------------------
        # Group adjacent blocks into paragraphs.
        # --------------------------------------------------

        paragraphs = (
            self._group_adjacent_blocks(
                paragraph_blocks
            )
        )

        # --------------------------------------------------
        # Translate and render paragraphs.
        # --------------------------------------------------

        for paragraph in paragraphs:

            text = paragraph["text"]

            rect = paragraph["rect"]

            font_size = paragraph[
                "font_size"
            ]

            print(
                "Translating paragraph:",
                repr(text[:100]),
            )

            translated = (
                translation_service.translate_text(
                    text=text,
                    target_language=target_language,
                    source_language=source_language,
                )
            )

            if not translated:
                continue

            self._insert_text_in_rect(
                output_page=output_page,
                rect=rect,
                text=translated,
                font_size=font_size,
            )

    # ======================================================
    # TABLE TRANSLATION
    # ======================================================

    def _translate_table(
        self,
        source_page,
        output_page,
        table,
        target_language,
        source_language,
    ):

        print(
            "Translating table..."
        )

        # --------------------------------------------------
        # PyMuPDF table extraction normally provides:
        #
        # table.bbox
        # table.rows
        #
        # Each row contains cells with bounding boxes.
        #
        # We use the detected table geometry to recreate
        # the table on the output page.
        # --------------------------------------------------

        table_bbox = fitz.Rect(
            table.bbox
        )

        rows = getattr(
            table,
            "rows",
            [],
        )

        if not rows:

            print(
                "No rows found in table."
            )

            return

        # --------------------------------------------------
        # Draw outer table border
        # --------------------------------------------------

        output_page.draw_rect(
            table_bbox,
            color=(0, 0, 0),
            width=0.7,
        )

        # --------------------------------------------------
        # Process rows and cells
        # --------------------------------------------------

        for row_index, row in enumerate(
            rows
        ):

            cells = getattr(
                row,
                "cells",
                [],
            )

            if not cells:
                continue

            for column_index, cell in enumerate(
                cells
            ):

                if cell is None:
                    continue

                cell_rect = fitz.Rect(
                    cell
                )

                # ------------------------------------------
                # Draw cell border
                # ------------------------------------------

                output_page.draw_rect(
                    cell_rect,
                    color=(0, 0, 0),
                    width=0.5,
                )

                # ------------------------------------------
                # Extract cell text from original page
                # ------------------------------------------

                cell_text = self._extract_text_from_rect(
                    source_page,
                    cell_rect,
                )

                if not cell_text.strip():

                    continue

                print(
                    f"Table cell "
                    f"[{row_index}, "
                    f"{column_index}]:",
                    repr(cell_text),
                )

                # ------------------------------------------
                # Translate cell
                # ------------------------------------------

                translated = (
                    translation_service.translate_text(
                        text=cell_text,
                        target_language=target_language,
                        source_language=source_language,
                    )
                )

                if not translated:
                    continue

                # ------------------------------------------
                # Add padding so text does not touch the
                # cell border.
                # ------------------------------------------

                text_rect = fitz.Rect(
                    cell_rect.x0 + 3,
                    cell_rect.y0 + 2,
                    cell_rect.x1 - 3,
                    cell_rect.y1 - 2,
                )

                # ------------------------------------------
                # Determine cell font size.
                # ------------------------------------------

                font_size = self._get_font_size_from_rect(
                    source_page,
                    cell_rect,
                )

                self._insert_text_in_rect(
                    output_page=output_page,
                    rect=text_rect,
                    text=translated,
                    font_size=font_size,
                    align=0,
                )

    # ======================================================
    # EXTRACT TEXT FROM RECTANGLE
    # ======================================================

    def _extract_text_from_rect(
        self,
        page,
        rect,
    ):

        text = page.get_text(
            "text",
            clip=rect,
        )

        if not text:
            return ""

        return text.strip()

    # ======================================================
    # GET FONT SIZE FROM RECTANGLE
    # ======================================================

    def _get_font_size_from_rect(
        self,
        page,
        rect,
    ):

        try:

            data = page.get_text(
                "dict",
                clip=rect,
            )

            sizes = []

            for block in data.get(
                "blocks",
                [],
            ):

                if block.get("type") != 0:
                    continue

                for line in block.get(
                    "lines",
                    [],
                ):

                    for span in line.get(
                        "spans",
                        [],
                    ):

                        size = span.get(
                            "size"
                        )

                        if size:
                            sizes.append(
                                size
                            )

            if sizes:

                return max(
                    7,
                    min(
                        max(sizes),
                        18,
                    ),
                )

        except Exception:
            pass

        return 10

    # ======================================================
    # GROUP ADJACENT BLOCKS
    # ======================================================

    def _group_adjacent_blocks(
        self,
        blocks,
    ):

        if not blocks:
            return []

        # --------------------------------------------------
        # Sort blocks top-to-bottom, left-to-right.
        # --------------------------------------------------

        blocks = sorted(
            blocks,
            key=lambda item: (
                item["rect"].y0,
                item["rect"].x0,
            ),
        )

        paragraphs = []

        current = None

        for block in blocks:

            rect = block["rect"]

            if current is None:

                current = {
                    "rect": fitz.Rect(
                        rect
                    ),
                    "text": block["text"],
                    "font_size": block[
                        "font_size"
                    ],
                }

                continue

            current_rect = current[
                "rect"
            ]

            # --------------------------------------------------
            # Vertical gap between blocks.
            # --------------------------------------------------

            vertical_gap = (
                rect.y0
                - current_rect.y1
            )

            # --------------------------------------------------
            # Horizontal overlap.
            # --------------------------------------------------

            overlap = self._horizontal_overlap(
                current_rect,
                rect,
            )

            # --------------------------------------------------
            # Determine whether blocks belong to the same
            # paragraph.
            # --------------------------------------------------

            same_paragraph = (

                vertical_gap <= max(
                    12,
                    current[
                        "font_size"
                    ] * 0.9,
                )

                and overlap > 0
            )

            if same_paragraph:

                current[
                    "text"
                ] += " " + block[
                    "text"
                ]

                current[
                    "rect"
                ] = self._union_rects(
                    current[
                        "rect"
                    ],
                    rect,
                )

                current[
                    "font_size"
                ] = max(
                    current[
                        "font_size"
                    ],
                    block[
                        "font_size"
                    ],
                )

            else:

                paragraphs.append(
                    current
                )

                current = {
                    "rect": fitz.Rect(
                        rect
                    ),
                    "text": block["text"],
                    "font_size": block[
                        "font_size"
                    ],
                }

        if current is not None:

            paragraphs.append(
                current
            )

        return paragraphs

    # ======================================================
    # HORIZONTAL OVERLAP
    # ======================================================

    def _horizontal_overlap(
        self,
        rect1,
        rect2,
    ):

        left = max(
            rect1.x0,
            rect2.x0,
        )

        right = min(
            rect1.x1,
            rect2.x1,
        )

        return max(
            0,
            right - left,
        )

    # ======================================================
    # RECT UNION
    #
    # We deliberately do NOT use:
    #
    # rect.union(...)
    #
    # because your installed PyMuPDF Rect object does not
    # provide that method.
    # ======================================================

    def _union_rects(
        self,
        rect1,
        rect2,
    ):

        return fitz.Rect(
            min(
                rect1.x0,
                rect2.x0,
            ),
            min(
                rect1.y0,
                rect2.y0,
            ),
            max(
                rect1.x1,
                rect2.x1,
            ),
            max(
                rect1.y1,
                rect2.y1,
            ),
        )

    # ======================================================
    # CHECK TABLE INTERSECTION
    # ======================================================

    def _rect_intersects_table(
        self,
        rect,
        table_rects,
    ):

        for table_rect in table_rects:

            # --------------------------------------------------
            # Calculate intersection manually.
            # --------------------------------------------------

            x_overlap = (
                min(
                    rect.x1,
                    table_rect.x1,
                )
                - max(
                    rect.x0,
                    table_rect.x0,
                )
            )

            y_overlap = (
                min(
                    rect.y1,
                    table_rect.y1,
                )
                - max(
                    rect.y0,
                    table_rect.y0,
                )
            )

            if (
                x_overlap > 0
                and y_overlap > 0
            ):

                return True

        return False

    # ======================================================
    # INSERT TEXT INSIDE RECTANGLE
    # ======================================================

    def _insert_text_in_rect(
        self,
        output_page,
        rect,
        text,
        font_size,
        align=0,
    ):

        # --------------------------------------------------
        # Start with original font size.
        # --------------------------------------------------

        font_size = max(
            7,
            min(
                font_size,
                18,
            ),
        )

        # --------------------------------------------------
        # Use insert_textbox so long Hindi/Marathi text can
        # wrap instead of being written outside the page.
        # --------------------------------------------------

        while font_size >= 7:

            result = output_page.insert_textbox(
                rect,
                text,
                fontsize=font_size,
                fontname="NotoDevanagari",
                align=align,
                lineheight=1.15,
            )

            # --------------------------------------------------
            # PyMuPDF returns a negative value when the text
            # does not fit in the textbox.
            # --------------------------------------------------

            if result >= 0:

                return

            font_size -= 0.5

        # --------------------------------------------------
        # Last fallback.
        #
        # This prevents a translation from disappearing
        # completely when the text is much longer than the
        # original text.
        # --------------------------------------------------

        output_page.insert_textbox(
            rect,
            text,
            fontsize=7,
            fontname="NotoDevanagari",
            align=align,
            lineheight=1.15,
        )


pdf_handler = PdfHandler()