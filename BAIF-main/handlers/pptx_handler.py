from pptx import Presentation

from services.translation_service import translation_service


class PptxHandler:

    def translate(
        self,
        input_file,
        output_file,
        target_language,
    ):
        presentation = Presentation(input_file)

        # ---------------------------------------------------------
        # PROCESS ALL SLIDES
        # ---------------------------------------------------------
        for slide in presentation.slides:

            for shape in slide.shapes:

                self._process_shape(
                    shape,
                    target_language,
                )

        presentation.save(output_file)

    # =============================================================
    # PROCESS SHAPE
    # =============================================================

    def _process_shape(
        self,
        shape,
        target_language,
    ):

        # ---------------------------------------------------------
        # TEXT BOX / PLACEHOLDER / SHAPE WITH TEXT
        # ---------------------------------------------------------
        if hasattr(shape, "text_frame") and shape.has_text_frame:

            self._translate_text_frame(
                shape.text_frame,
                target_language,
            )

        # ---------------------------------------------------------
        # TABLE
        # ---------------------------------------------------------
        if shape.has_table:

            table = shape.table

            for row in table.rows:

                for cell in row.cells:

                    self._translate_text_frame(
                        cell.text_frame,
                        target_language,
                    )

        # ---------------------------------------------------------
        # GROUP SHAPE
        # ---------------------------------------------------------
        if shape.shape_type == 6:  # GROUP

            for child_shape in shape.shapes:

                self._process_shape(
                    child_shape,
                    target_language,
                )

    # =============================================================
    # TEXT FRAME
    # =============================================================

    def _translate_text_frame(
        self,
        text_frame,
        target_language,
    ):

        for paragraph in text_frame.paragraphs:

            original_text = paragraph.text

            if not original_text.strip():
                continue

            translated = translation_service.translate_text(
                original_text,
                target_language,
            )

            if not translated:
                continue

            self._replace_paragraph_text(
                paragraph,
                translated,
            )

    # =============================================================
    # PARAGRAPH
    # =============================================================

    def _replace_paragraph_text(
        self,
        paragraph,
        translated_text,
    ):

        runs = paragraph.runs

        # ---------------------------------------------------------
        # No runs
        # ---------------------------------------------------------
        if not runs:

            run = paragraph.add_run()
            run.text = translated_text

            return

        # ---------------------------------------------------------
        # Single run
        # ---------------------------------------------------------
        if len(runs) == 1:

            runs[0].text = translated_text

            return

        # ---------------------------------------------------------
        # Save formatting information
        # ---------------------------------------------------------
        formatting = []

        for run in runs:

            font = run.font

            formatting.append(
                {
                    "bold": font.bold,
                    "italic": font.italic,
                    "underline": font.underline,
                    "font_size": font.size,
                    "font_name": font.name,
                }
            )

        # ---------------------------------------------------------
        # Original run lengths
        # ---------------------------------------------------------
        original_lengths = [
            len(run.text)
            for run in runs
        ]

        total_length = sum(original_lengths)

        # ---------------------------------------------------------
        # Clear existing text
        # ---------------------------------------------------------
        for run in runs:
            run.text = ""

        # ---------------------------------------------------------
        # No meaningful original text
        # ---------------------------------------------------------
        if total_length == 0:

            runs[0].text = translated_text

            return

        # ---------------------------------------------------------
        # Distribute translated text across runs
        # ---------------------------------------------------------
        translated_length = len(translated_text)

        current_position = 0

        for index, run in enumerate(runs):

            if index == len(runs) - 1:

                end_position = translated_length

            else:

                ratio = (
                    original_lengths[index]
                    / total_length
                )

                chunk_length = round(
                    translated_length * ratio
                )

                end_position = (
                    current_position
                    + chunk_length
                )

            run.text = translated_text[
                current_position:end_position
            ]

            # Restore formatting
            fmt = formatting[index]

            run.font.bold = fmt["bold"]
            run.font.italic = fmt["italic"]
            run.font.underline = fmt["underline"]
            run.font.size = fmt["font_size"]
            run.font.name = fmt["font_name"]

            current_position = end_position


pptx_handler = PptxHandler()