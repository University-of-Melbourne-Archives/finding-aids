# src/postprocess/inherit_series.py

import pandas as pd
import re


def _is_non_empty(value) -> bool:
    """Return True if value is a meaningful, non-empty value."""
    if value is None:
        return False
    s = str(value).strip()
    if s == "" or s.lower() == "nan":
        return False
    return True


def _parse_path_cell(val):
    """
    Convert a cell from `hierarchy_path` into a tuple of ints or None.

    Handles:
      - tuples already in-memory: (5, 1)
      - strings: "(5, 1)", "(5,)", "(101, 1)"
      - empty / NaN / "None" -> None
    """
    if isinstance(val, tuple):
        return val

    if val is None:
        return None

    s = str(val).strip()
    if s == "" or s.lower() in {"none", "nan"}:
        return None

    m = re.fullmatch(r"\(\s*\d+(?:\s*,\s*\d+)*\s*\)", s)
    if not m:
        return None

    inner = s[1:-1].strip()
    if inner == "":
        return None

    parts = [p.strip() for p in inner.split(",")]
    try:
        nums = tuple(int(p) for p in parts if p != "")
        return nums if nums else None
    except ValueError:
        return None


def inherit_series(
    df: pd.DataFrame,
    path_col: str = "hierarchy_path",
    series_col: str = "series_value",
    series_note_col: str = "series_notes_value",
    out_series_col: str = "series_value_inherited",
    out_series_note_col: str = "series_notes_inherited",
) -> pd.DataFrame:
    """
    Inherit `series_value` and `series_notes_value` from the *nearest previous parent*
    in the hierarchy.

    Forward-only logic:
      - Iterate rows from top to bottom.
      - Maintain map: seen_path -> (series_value, series_note) for rows that
        explicitly define a series (have their own non-empty value or note).
      - For current row with path P:
          * Check ancestor paths among those already seen:
              P[:-1], P[:-2], ... until empty.
          * Inherit that series / note if own values are missing.
      - Only rows that have their own series/notes are added to the map
        (purely inherited rows do NOT become new parents).

    Also reorders columns so they appear as:
        ... series_col, out_series_col, series_note_col, out_series_note_col, ...
    """

    df = df.copy()

    # Normalize path to tuples
    norm_paths = []
    for val in df[path_col]:
        norm_paths.append(_parse_path_cell(val))
    df[path_col] = norm_paths

    parent_series_map = {}  # path -> (own_series, own_note)

    out_series_vals = []
    out_series_notes = []

    for _, row in df.iterrows():
        path = row.get(path_col)
        own_series = row.get(series_col)
        own_note = row.get(series_note_col)

        # 1. Find nearest previous ancestor series
        inherited_series, inherited_note = None, None
        if isinstance(path, tuple):
            cur = path[:-1]  # start from immediate parent
            while cur:
                if cur in parent_series_map:
                    inherited_series, inherited_note = parent_series_map[cur]
                    break
                cur = cur[:-1]

        # 2. Decide final values
        final_series = own_series if _is_non_empty(own_series) else inherited_series
        final_note = own_note if _is_non_empty(own_note) else inherited_note

        out_series_vals.append(final_series)
        out_series_notes.append(final_note)

        # 3. Update map for future rows (only rows with their own series/note)
        if isinstance(path, tuple) and (
            _is_non_empty(own_series) or _is_non_empty(own_note)
        ):
            parent_series_map[path] = (own_series, own_note)

    df[out_series_col] = out_series_vals
    df[out_series_note_col] = out_series_notes

    # 4. Reorder columns: series_value, series_value_inherited,
    #    series_notes_value, series_notes_inherited
    cols = list(df.columns)

    def move_after(base, new):
        if base in cols and new in cols:
            cols.remove(new)
            idx = cols.index(base)
            cols.insert(idx + 1, new)

    # move in two steps: value + inherited, notes + inherited
    move_after(series_col, out_series_col)
    move_after(series_note_col, out_series_note_col)

    df = df[cols]
    return df
