import re
from pathlib import Path


ACTIVE_CODE_ROOTS = (Path("app/api/v1"), Path("app/modules"))
LEGACY_SERVICE_IMPORT = re.compile(r"(?:from|import)\s+app\.services(?:\.|\s)")


def test_active_api_and_modules_do_not_import_legacy_services():
    violations = []
    for root in ACTIVE_CODE_ROOTS:
        for source_file in root.rglob("*.py"):
            if LEGACY_SERVICE_IMPORT.search(source_file.read_text(encoding="utf-8")):
                violations.append(str(source_file))

    assert violations == []
