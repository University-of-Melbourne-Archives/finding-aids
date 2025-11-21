# tests/test_style_and_handlers.py
from finding_aids_ocr.processing.style_detector import StyleDetector


def test_style_detector_parenthesis(sample_chunk_result):
    style = StyleDetector().detect(sample_chunk_result)
    assert style == "parenthesis"


def test_parenthesis_handler_extract_state(sample_chunk_result, parenthesis_handler):
    state = parenthesis_handler.extract_state(sample_chunk_result)

    # Should track last reference/title etc.
    assert state["hierarchy_style"] == "parenthesis"
    assert state["last_reference"] == "25.(4)"
    assert state["current_series"] == "Series A"
    assert state["current_unit"] == "Unit 1"
    assert state["last_title"] == "Correspondence"


def test_parenthesis_handler_validate_reference(parenthesis_handler):
    valid = parenthesis_handler.validate_reference("25.(3)")
    assert valid["valid"]

    invalid = parenthesis_handler.validate_reference("25/3")
    assert not invalid["valid"]
    assert "pattern" in (invalid.get("issue") or "").lower()
