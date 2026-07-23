"""文件解析服务测试"""

import os
import tempfile
from app.services.file_parser import extract_text, read_text_file, is_multimodal_model


def test_read_text_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Hello World")
        tmp = f.name
    try:
        result = read_text_file(tmp)
        assert result == "Hello World"
    finally:
        os.unlink(tmp)


def test_read_text_file_not_found():
    assert read_text_file("/nonexistent/file.txt") is None


def test_extract_unsupported_format():
    assert extract_text("/tmp/test.xyz") is None


def test_is_multimodal_model():
    assert is_multimodal_model("qwen-vl-plus") is True
    assert is_multimodal_model("gpt-4o") is False
    assert is_multimodal_model("glm-4v") is True
    assert is_multimodal_model("deepseek-chat") is False
