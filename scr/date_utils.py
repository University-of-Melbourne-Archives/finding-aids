# scr/date_utils.py
# -*- coding: utf-8 -*-
"""
normalize_date(raw) -> (dates_sortable: 'YYYY-MM-DD', precision: 'complete'|'incomplete')

Rules:
- 'No date'/ 'n.d.'  => incomplete (returns 9999-12-31)
- Trailing '-'        => incomplete (returns 9999-12-31)
- Multi-dates ';'     => use FIRST segment
- Ranges ('-' or ' to ') => use START (left side) for dates_sortable; completeness is judged
  on that left side only
- 'complete' only when day-of-month **and** month are present (or numeric dd/mm/yyyy).
  Everything else (year-only, month-year, circa, fuzzy OCR, etc.) is 'incomplete'.
"""

import re
from typing import Tuple, Optional
from datetime import datetime

import dateparser

# Quick gates
_RE_NO_DATE    = re.compile(r"^\s*(?:no\s*date|n\.d\.?)\s*[\.\,;]?\s*$", re.I)
_RE_INCOMPLETE = re.compile(r"-\s*[\.\,;]?\s*$")  # dangling dash at end

# Month/day detection for "completeness"
_MONTH_RE = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
    r"|january|february|march|april|june|july|august|september|october|november|december)\.?\b",
    re.I,
)
_DAY_RE = re.compile(r"(?<!\d)([0-3]?\d)(?:st|nd|rd|th)?(?!\d)")
_NUMERIC_DATE_RE = re.compile(r"\b\d{1,2}[\/\.\-]\d{1,2}[\/\.\-]\d{2,4}\b")

SETTINGS = {
    "PREFER_DAY_OF_MONTH": "first",
    "DATE_ORDER": "DMY",
    "REQUIRE_PARTS": ["year"],
    "STRICT_PARSING": False,
    "RETURN_AS_TIMEZONE_AWARE": False,
    "RELATIVE_BASE": datetime(1900, 1, 1),
}

def _clean(s: str) -> str:
    s = s.strip().strip("“”\"'[]() ")
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s)
    return s

def _left_segment(text: str) -> str:
    """Return the portion before a range dash/‘to’, then before a ';'."""
    t = text
    low = t.lower()
    if " to " in low:
        t = t[: low.find(" to ")]
    elif "-" in t:
        t = t.split("-", 1)[0]
    if ";" in t:
        t = t.split(";", 1)[0]
    return t.strip()

def _is_complete(seg: str) -> bool:
    """Heuristic: has a day token and a month token OR looks like dd/mm/yyyy."""
    return bool(_NUMERIC_DATE_RE.search(seg) or (_DAY_RE.search(seg) and _MONTH_RE.search(seg)))

def normalize_date(raw: Optional[str]) -> Tuple[str, str]:
    if raw is None:
        return "9999-12-31", "incomplete"

    s = _clean(str(raw))
    if not s or _RE_NO_DATE.match(s):
        return "9999-12-31", "incomplete"
    if _RE_INCOMPLETE.search(s):
        return "9999-12-31", "incomplete"

    left = _left_segment(s)

    dt = dateparser.parse(left, settings=SETTINGS, languages=["en"])
    if not dt:
        return "9999-12-31", "incomplete"

    iso = f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"
    return iso, ("complete" if _is_complete(left) else "incomplete")
