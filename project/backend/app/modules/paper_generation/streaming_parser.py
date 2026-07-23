import json
import re


def extract_question_from_buffer(buffer: str, index: int) -> dict | None:
    """Return one completed question object from an incremental JSON response."""
    questions_match = re.search(r'"questions"\s*:\s*\[', buffer)
    if not questions_match:
        return None

    position = questions_match.end()
    depth = 0
    object_start = -1
    object_index = -1
    while position < len(buffer):
        char = buffer[position]
        if char == "{":
            if depth == 0:
                object_index += 1
                object_start = position
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and object_start >= 0:
                if object_index == index:
                    raw_question = buffer[object_start : position + 1]
                    try:
                        return json.loads(raw_question)
                    except json.JSONDecodeError:
                        return _parse_question_leniently(raw_question)
                object_start = -1
        elif char == '"':
            position = _skip_string(buffer, position)
        position += 1
    return None


def find_complete_json(buffer: str) -> dict | None:
    """Return the first complete JSON object, ignoring braces inside strings."""
    depth = 0
    object_start = -1
    position = 0
    while position < len(buffer):
        char = buffer[position]
        if char == "{":
            if object_start < 0:
                object_start = position
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and object_start >= 0:
                try:
                    return json.loads(buffer[object_start : position + 1])
                except json.JSONDecodeError:
                    return None
        elif char == '"':
            position = _skip_string(buffer, position)
        position += 1
    return None


def _skip_string(value: str, position: int) -> int:
    position += 1
    while position < len(value):
        if value[position] == "\\":
            position += 2
            continue
        if value[position] == '"':
            return position
        position += 1
    return position


def _parse_question_leniently(raw_question: str) -> dict | None:
    try:
        question: dict = {}
        for key in ("index", "type", "score", "content", "options", "answer", "analysis"):
            pattern = r'"' + key + r'"\s*:\s*("(?:[^"\\]|\\.)*"|\[[^\]]*\]|-?\d+(?:\.\d+)?|true|false|null)'
            match = re.search(pattern, raw_question)
            if not match:
                continue
            value = match.group(1)
            try:
                question[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                question[key] = value.strip('"')
        return question if "index" in question and "content" in question else None
    except Exception:
        return None
