import os
from typing import Optional


def extract_text_from_docx(file_path: str) -> Optional[str]:
    try:
        from docx import Document

        document = Document(file_path)
        return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
    except Exception:
        return None


def extract_text_from_pdf(file_path: str) -> Optional[str]:
    try:
        import fitz

        document = fitz.open(file_path)
        return "\n".join(page.get_text() for page in document)
    except Exception:
        return None


def read_text_file(file_path: str) -> Optional[str]:
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except Exception:
        return None


def extract_text(file_path: str) -> Optional[str]:
    extension = os.path.splitext(file_path)[1].lower()
    if extension == ".docx":
        return extract_text_from_docx(file_path)
    if extension == ".pdf":
        return extract_text_from_pdf(file_path)
    if extension == ".txt":
        return read_text_file(file_path)
    return None


def is_multimodal_model(model_name: str) -> bool:
    model = model_name.lower()
    return any(keyword in model for keyword in ("vision", "vl", "vl-plus", "glm-4v", "qwen-vl"))
