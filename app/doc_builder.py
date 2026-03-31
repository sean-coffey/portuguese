from docx import Document
from docx.shared import Inches
from app.config import OUTPUT_DIR
import os


def build_docx(items, title="Gerador de Imagens, Protótipo v1", filename="output.docx"):
    doc = Document()
    doc.add_heading(title, 0)

    table = doc.add_table(rows=len(items), cols=2)

    for i, item in enumerate(items):
        row = table.rows[i]

        phrase_text = item.normalized

        if item.gloss_en:
            phrase_text += f"\nEnglish: {item.gloss_en}"

        if item.teacher_review:
            phrase_text += f"\nReview suggested ({item.visual_type})"

        row.cells[0].text = phrase_text

        paragraph = row.cells[1].paragraphs[0]
        run = paragraph.add_run()
        run.add_picture(item.image_path, width=Inches(3))

    output_path = os.path.join(OUTPUT_DIR, filename)
    doc.save(output_path)
    return output_path