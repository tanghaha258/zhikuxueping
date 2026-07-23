import importlib.util


def test_legacy_file_parser_reexports_shared_implementation():
    assert importlib.util.find_spec("app.shared.file_parsing") is not None

    from app.services import file_parser
    from app.shared import file_parsing

    assert file_parser.extract_text is file_parsing.extract_text
    assert file_parser.read_text_file is file_parsing.read_text_file
