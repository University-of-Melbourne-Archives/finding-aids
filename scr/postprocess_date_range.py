#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
postprocess_date_range.py

Add range-aware date columns to a UMA-style Excel:
- Start_Date, End_Date
- Start_Date_Sortable, End_Date_Sortable
- Start_Date_Complete, End_Date_Complete

Keeps existing:
- Dates_Sortable, Date_Complete

Usage:
  python3 postprocess_date_range.py --xlsx /path/to/file.xlsx [--sheet SHEETNAME] [--no_backup]
"""

import argparse
import re
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd

# Import your existing normalizer (left-segment + completeness)
try:
    from date_utils import normalize_date          # if run: python3 postprocess_date_range.py
except ModuleNotFoundError:
    from scr.date_utils import normalize_date      # if run: python3 -m scr.postprocess_date_range


# ----------------------------
# Configuration
# ----------------------------

SHEET_CANDIDATES = ["Records", "Record", "Items", "Sheet1", "Sheet 1"]

# Month dictionary (tolerates abbreviations with/without dot)
_MONTHS = {
    "jan": "Jan", "jan.": "Jan",
    "feb": "Feb", "feb.": "Feb",
    "mar": "Mar", "mar.": "Mar",
    "apr": "Apr", "apr.": "Apr",
    "may": "May",
    "jun": "Jun", "jun.": "Jun",
    "jul": "Jul", "jul.": "Jul",
    "aug": "Aug", "aug.": "Aug",
    "sep": "Sep", "sep.": "Sep", "sept": "Sep", "sept.": "Sep",
    "oct": "Oct", "oct.": "Oct",
    "nov": "Nov", "nov.": "Nov",
    "dec": "Dec", "dec.": "Dec",
}

_YEAR_RE  = re.compile(r"\b(1[5-9]\d{2}|20\d{2}|21\d{2})\b")  # 1500–2199; adjust if needed
_DAY_RE   = re.compile(r"\b([1-9]|[12]\d|3[01])\b")
_MONTH_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in _MONTHS.keys()) + r")\b", re.IGNORECASE)

# Top-level connectors implying ranges / endpoints
_SPLIT_RANGE_RE = re.compile(r"\s*(?:–|—|-|\bto\b|\band\b|&)\s*", re.IGNORECASE)


# ----------------------------
# Helpers
# ----------------------------

def pick_sheet(xlsx_path: str, preferred: Optional[str] = None) -> str:
    """Return an existing sheet name.
    Priority: preferred (exact or case-insensitive) -> candidates -> first sheet.
    """
    xl = pd.ExcelFile(xlsx_path)  # openpyxl for .xlsx
    names = xl.sheet_names
    if preferred:
        if preferred in names:
            return preferred
        lowmap = {n.lower(): n for n in names}
        if preferred.lower() in lowmap:
            return lowmap[preferred.lower()]
    lowmap = {n.lower(): n for n in names}
    for cand in SHEET_CANDIDATES:
        if cand in names:
            return cand
        if cand.lower() in lowmap:
            return lowmap[cand.lower()]
    return names[0]


def _ensure_text_dtype(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype("string")
    return df


def _clean_piece(s: str) -> str:
    s = (s or "").strip()
    return s.rstrip(" .;,/")  # common trailing punctuation in finding aids


def _find_year(s: str) -> Optional[str]:
    m = _YEAR_RE.search(s)
    return m.group(1) if m else None


def _find_month(s: str) -> Optional[str]:
    m = _MONTH_RE.search(s)
    if not m:
        return None
    return _MONTHS[m.group(1).lower()]


def _find_last_day(s: str) -> Optional[str]:
    matches = list(_DAY_RE.finditer(s))
    return matches[-1].group(1) if matches else None


def _reconstruct_date(piece: str, defaults: dict) -> str:
    """
    Build a standalone, human-readable date string (e.g., '14 Oct 1839') using info
    from 'piece' plus defaults (year/month/day) when missing.
    The result is fed into normalize_date().
    """
    piece = _clean_piece(piece)
    y = _find_year(piece)  or defaults.get("year")
    m = _find_month(piece) or defaults.get("month")
    d = _find_last_day(piece) or defaults.get("day")

    if y and m and d:
        return f"{int(d)} {m} {y}"
    if y and m:
        return f"{m} {y}"
    if y and d and defaults.get("month"):
        return f"{int(d)} {defaults['month']} {y}"
    if m and d and defaults.get("year"):
        return f"{int(d)} {m} {defaults['year']}"
    if y:
        return y
    if m and defaults.get("year"):
        return f"{m} {defaults['year']}"
    return piece  # fall back; normalize_date will still try


def _handle_intra_piece_day_span(piece: str, whole: str) -> Optional[Tuple[str, str]]:
    """
    Catch things like '1839, 14-15 Oct.' inside a single piece.
    Returns (start_str, end_str) or None if not applicable.
    """
    p = _clean_piece(piece)
    m = re.search(r"\b([1-9]|[12]\d|3[01])\s*[-–—]\s*([1-9]|[12]\d|3[01])\b", p)
    if not m:
        return None
    d1, d2 = m.group(1), m.group(2)
    month_here = _find_month(p) or _find_month(whole)
    year_here  = _find_year(p)  or _find_year(whole)
    left  = " ".join(x for x in [str(int(d1)), month_here, year_here] if x)
    right = " ".join(x for x in [str(int(d2)), month_here, year_here] if x)
    return left.strip(), right.strip()


def split_date_range(raw: str) -> Tuple[str, str]:
    """
    Split a raw 'Dates' string into (start_text, end_text) with context carried.
    Handles connectors: '-', long dashes, 'to', 'and', '&'.
    Also handles intra-piece day spans like '14-15 Oct.'.
    """
    if not raw:
        return "", ""
    s = str(raw).replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s).strip().rstrip(" .;,/")

    pieces = [p for p in _SPLIT_RANGE_RE.split(s) if p and not p.isspace()]
    if not pieces:
        return "", ""

    # Single piece: try intra-piece day span first
    if len(pieces) == 1:
        hit = _handle_intra_piece_day_span(pieces[0], s)
        if hit:
            return hit
        # Single, not a range
        single = _reconstruct_date(pieces[0], {"year": _find_year(s), "month": _find_month(s)})
        return single, single

    # General multi-piece case: use first and last as endpoints, borrow missing context
    global_year  = _find_year(s)
    global_month = _find_month(s)
    start = _reconstruct_date(pieces[0], {"year": global_year, "month": global_month})
    end   = _reconstruct_date(pieces[-1], {"year": global_year, "month": global_month})
    return start, end


# ----------------------------
# Dataframe mutation
# ----------------------------

def _add_or_update_date_cols(df: pd.DataFrame) -> pd.DataFrame:
    if "Dates" not in df.columns:
        raise RuntimeError("Expected a 'Dates' column in the XLSX sheet.")

    # Keep legacy columns (left-segment normalization)
    dates_sortable: List[str] = []
    date_complete: List[bool] = []

    # New columns
    start_dates: List[str] = []
    end_dates: List[str] = []
    start_sortables: List[str] = []
    end_sortables: List[str] = []
    start_completes: List[bool] = []
    end_completes: List[bool] = []

    for raw in df["Dates"].tolist():
        txt = "" if pd.isna(raw) else str(raw)

        # (1) Original single-date normalization (left side only)
        norm_single, prec_single = normalize_date(txt)
        dates_sortable.append(norm_single)
        date_complete.append(prec_single == "complete")

        # (2) Range-aware: produce explicit start/end text, then normalize each
        start_text, end_text = split_date_range(txt)

        norm_start, prec_start = normalize_date(start_text) if start_text else ("", "incomplete")
        norm_end,   prec_end   = normalize_date(end_text)   if end_text   else ("", "incomplete")

        start_dates.append(start_text)
        end_dates.append(end_text)
        start_sortables.append(norm_start)
        end_sortables.append(norm_end)
        start_completes.append(prec_start == "complete")
        end_completes.append(prec_end == "complete")

    # Insert/update legacy columns next to Dates
    if "Dates_Sortable" in df.columns:
        df["Dates_Sortable"] = dates_sortable
    else:
        insert_at = df.columns.get_loc("Dates") + 1
        df.insert(insert_at, "Dates_Sortable", dates_sortable)

    if "Date_Complete" in df.columns:
        df["Date_Complete"] = date_complete
    else:
        insert_at = df.columns.get_loc("Dates_Sortable") + 1
        df.insert(insert_at, "Date_Complete", date_complete)

    # Then add the six new columns immediately after Date_Complete
    def _insert_or_update(colname: str, values: list):
        if colname in df.columns:
            df[colname] = values
        else:
            idx = df.columns.get_loc("Date_Complete") + 1
            df.insert(idx, colname, values)

    _insert_or_update("Start_Date", start_dates)
    _insert_or_update("End_Date", end_dates)
    _insert_or_update("Start_Date_Sortable", start_sortables)
    _insert_or_update("End_Date_Sortable", end_sortables)
    _insert_or_update("Start_Date_Complete", start_completes)
    _insert_or_update("End_Date_Complete", end_completes)

    return df


# ----------------------------
# Excel writer (styled)
# ----------------------------

def _write_styled_xlsx(df: pd.DataFrame, out_path: Path, sheet_name: str):
    out_path = Path(out_path)
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)

        wb = writer.book
        ws = writer.sheets[sheet_name]

        text_fmt = wb.add_format({"num_format": "@"})
        header_fmt = wb.add_format({"bold": True, "text_wrap": True, "valign": "vcenter"})
        ws.set_row(0, 18, header_fmt)

        col_widths = {
            "Unit": 12,
            "Finding_Aid_Reference": 22,
            "Series_ID": 14,
            "Series_Title": 28,
            "Title_Description": 42,
            "Dates": 16,
            "Dates_Sortable": 16,
            "Date_Complete": 14,
            "Start_Date": 18,
            "End_Date": 18,
            "Start_Date_Sortable": 18,
            "End_Date_Sortable": 18,
            "Start_Date_Complete": 18,
            "End_Date_Complete": 18,
            "Series_Description": 32,
            "Series_Annotations": 28,
            "Item_Annotations": 32,
            "Hierarchy_Path": 28,
        }

        # keep everything as text so "9999-12-31" shows verbatim
        for idx, col in enumerate(df.columns):
            ws.set_column(idx, idx, col_widths.get(col, 24), text_fmt)

        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, len(df), len(df.columns) - 1)


# ----------------------------
# Runner
# ----------------------------

def run(xlsx_path: str, sheet: Optional[str] = None, backup: bool = True):
    xlsx = Path(xlsx_path)
    if not xlsx.exists():
        raise FileNotFoundError(xlsx)

    # Optional backup
    if backup:
        bak = xlsx.with_suffix(xlsx.suffix + ".bak")
        bak.write_bytes(xlsx.read_bytes())

    # Pick sheet
    selected_sheet = pick_sheet(str(xlsx), sheet)

    # Read, update, write back (overwrite original)
    df = pd.read_excel(xlsx, sheet_name=selected_sheet, dtype="string")
    df = _ensure_text_dtype(df, df.columns)
    df = _add_or_update_date_cols(df)
    _write_styled_xlsx(df, xlsx, selected_sheet)


def main():
    ap = argparse.ArgumentParser(
        description="Add range-aware date columns to a UMA .xlsx (in place)."
    )
    ap.add_argument("--xlsx", required=True, help="Path to the Excel file to update.")
    ap.add_argument("--sheet", default=None,
                    help="Worksheet name to use. If omitted, auto-detects.")
    ap.add_argument("--no_backup", action="store_true",
                    help="Do not write a .bak backup before overwriting.")
    args = ap.parse_args()

    run(args.xlsx, sheet=args.sheet, backup=not args.no_backup)


if __name__ == "__main__":
    main()
