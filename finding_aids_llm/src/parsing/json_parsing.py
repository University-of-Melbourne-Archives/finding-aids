# src/parsing/json_parsing.py
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ParseIssue:
    """
    A structured record of something that went wrong while parsing.

    level:
        "chunk" -> problem with the whole chunk (e.g. JSON decode error)
        "item"  -> problem with a specific item inside items[]
    chunk_id:
        identifier for the chunk (e.g. "chunk1-5" or filename)
    item_index:
        0-based index into items[] if level == "item", else None
    message:
        human-readable description of what went wrong
    """
    level: str
    chunk_id: str
    message: str
    item_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Fields we expect on each item from the LLM JSON
EXPECTED_ITEM_FIELDS = [
    "group",
    "group_notes",
    "series",
    "series_notes",
    "unit",
    "finding_aid_reference_raw",
    "text",
    "start_date_original",
    "end_date_original",
    "start_date_formatted",
    "end_date_formatted",
    "annotations",
]

# These should be dicts of the shape:
#   { "value": <str>, "confidence": <str or null> }
SCALAR_FIELDS = [
    "group",
    "group_notes",
    "series",
    "series_notes",
    "unit",
    "finding_aid_reference_raw",
    "text",
    "start_date_original",
    "end_date_original",
    "start_date_formatted",
    "end_date_formatted",
]


def _strip_json_fence(text: str) -> str:
    """
    Be defensive: if the model ever wraps JSON in ```json ... ``` fences,
    strip those off before json.loads.
    """
    t = text.strip()
    if not t.startswith("```"):
        return t

    lines = t.splitlines()
    # Drop first ```... line
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    # Drop last ``` line if present
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_chunk_text(
    raw_text: str,
    chunk_id: str,
    issues: Optional[List[ParseIssue]] = None,
) -> Tuple[List[Dict[str, Any]], List[ParseIssue]]:
    """
    Parse the raw LLM output for a single chunk.

    - Returns (valid_items, issues)
    - If the whole chunk is malformed JSON, returns [] and records a single
      chunk-level ParseIssue.
    - If some items inside "items" are malformed, skips those items and
      records item-level ParseIssue entries, but keeps the others.

    Parameters
    ----------
    raw_text:
        The raw text produced by the LLM for this chunk.
    chunk_id:
        A human-readable identifier for logs (e.g. "chunk1-5").
    issues:
        Optional existing list of ParseIssue objects to append to.
    """
    if issues is None:
        issues = []

    cleaned = _strip_json_fence(raw_text)

    # 1. JSON decode
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        issues.append(
            ParseIssue(
                level="chunk",
                chunk_id=chunk_id,
                message=f"JSON decode error: {e}",
                item_index=None,
            )
        )
        return [], issues

    # 2. Top-level must be an object with "items": [...]
    if not isinstance(data, dict):
        issues.append(
            ParseIssue(
                level="chunk",
                chunk_id=chunk_id,
                message=f"Top-level JSON is {type(data).__name__}, expected object.",
                item_index=None,
            )
        )
        return [], issues

    items = data.get("items")
    if not isinstance(items, list):
        issues.append(
            ParseIssue(
                level="chunk",
                chunk_id=chunk_id,
                message="Missing or non-list `items` field on top-level object.",
                item_index=None,
            )
        )
        return [], issues

    valid_items: List[Dict[str, Any]] = []

    # 3. Validate each item; skip bad ones
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            issues.append(
                ParseIssue(
                    level="item",
                    chunk_id=chunk_id,
                    item_index=idx,
                    message=f"Item is {type(item).__name__}, expected object.",
                )
            )
            continue

        bad = False

        # 3a. Check required fields
        for field in EXPECTED_ITEM_FIELDS:
            if field not in item:
                issues.append(
                    ParseIssue(
                        level="item",
                        chunk_id=chunk_id,
                        item_index=idx,
                        message=f"Missing field `{field}`.",
                    )
                )
                bad = True
                break

        if bad:
            continue

        # 3b. annotations should be a list
        if not isinstance(item["annotations"], list):
            issues.append(
                ParseIssue(
                    level="item",
                    chunk_id=chunk_id,
                    item_index=idx,
                    message="`annotations` is not a list.",
                )
            )
            continue

        # 3c. scalar fields should be dicts with value/confidence
        for field in SCALAR_FIELDS:
            val = item.get(field)
            if not isinstance(val, dict):
                issues.append(
                    ParseIssue(
                        level="item",
                        chunk_id=chunk_id,
                        item_index=idx,
                        message=f"`{field}` is {type(val).__name__}, expected object.",
                    )
                )
                bad = True
                break
            if "value" not in val or "confidence" not in val:
                issues.append(
                    ParseIssue(
                        level="item",
                        chunk_id=chunk_id,
                        item_index=idx,
                        message=f"`{field}` missing `value` or `confidence` key.",
                    )
                )
                bad = True
                break

        if bad:
            continue

        # If we reach here, item passes all checks
        valid_items.append(item)

    return valid_items, issues
