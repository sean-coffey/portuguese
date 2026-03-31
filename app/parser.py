from docx import Document

def extract_phrases_from_docx(path: str) -> list[str]:
    doc = Document(path)
    phrases = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            phrases.append(text)

    return phrases