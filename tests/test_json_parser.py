# tests/test_json_parser.py
import json
import textwrap


def test_parse_fenced_json(json_parser):
    data = {"series": [], "unassigned_items": [], "document_notes": "ok"}
    raw = textwrap.dedent(
        f"""
        Here is your JSON:

        ```json
        {json.dumps(data)}
        ```
        """
    )
    parsed = json_parser.parse(raw)
    assert parsed == data


def test_parse_raw_json(json_parser):
    data = {"series": [], "unassigned_items": [], "document_notes": "ok"}
    raw = json.dumps(data)
    parsed = json_parser.parse(raw)
    assert parsed == data


def test_parse_invalid_returns_none(json_parser):
    raw = "not json at all"
    parsed = json_parser.parse(raw)
    assert parsed is None
