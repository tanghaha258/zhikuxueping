"""Compatibility exports for shared file parsing helpers."""

from app.shared.file_parsing import (
    extract_text,
    extract_text_from_docx,
    extract_text_from_pdf,
    is_multimodal_model,
    read_text_file,
)

__all__ = [
    "extract_text",
    "extract_text_from_docx",
    "extract_text_from_pdf",
    "is_multimodal_model",
    "read_text_file",
]
