from copy import deepcopy
import os

from docx import Document
from docx.shared import Inches
from app.config import OUTPUT_DIR, TEMPLATES_DIR


LOGO_PATH = os.path.join(OUTPUT_DIR, "logo.png")
TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, "template.docx")
TEACHER_NAME = "Sara Guimarães"


def replace_placeholder_in_paragraph(paragraph, placeholder, value):
    """
    Replace placeholder text without destroying formatting.

    This works even if the placeholder was split across multiple runs.
    It preserves the formatting of the first run in the paragraph.
    """
    full_text = "".join(run.text for run in paragraph.runs)

    if placeholder not in full_text:
        return

    new_text = full_text.replace(placeholder, value or "")

    if not paragraph.runs:
        paragraph.add_run(new_text)
        return

    for run in paragraph.runs:
        run.text = ""

    paragraph.runs[0].text = new_text


def build_docx(items, output_filename):
    doc = Document(TEMPLATE_PATH)
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    if not doc.tables:
        raise RuntimeError("Template must contain at least one table.")

    table = doc.tables[0]

    if not table.rows:
        raise RuntimeError("Template table must contain at least one row.")

    # First row is the prototype/template row
    template_row = table.rows[0]

    for item in items:
        new_row_element = deepcopy(template_row._element)
        table._element.append(new_row_element)
        row = table.rows[-1]

        # LEFT CELL: placeholders
        left_cell = row.cells[0]

        for paragraph in left_cell.paragraphs:
            replace_placeholder_in_paragraph(paragraph, "{{PHRASE}}", item.normalized)
            replace_placeholder_in_paragraph(
                paragraph,
                "{{GLOSS}}",
                item.gloss_en if item.gloss_en else ""
            )
            replace_placeholder_in_paragraph(
                paragraph,
                "{{NOTE}}",
                "(review suggested)" if getattr(item, "teacher_review", False) else ""
            )

        # RIGHT CELL: image
        right_cell = row.cells[1]
        img_paragraph = right_cell.paragraphs[0]
        run = img_paragraph.add_run()
        run.add_picture(item.image_path, width=Inches(3))

    # Remove the original prototype row
    table._element.remove(template_row._element)

    doc.save(output_path)
    return output_path