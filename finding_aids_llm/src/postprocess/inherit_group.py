# src/postprocess/inherit_group_notes.py

import pandas as pd
import re


def _is_non_empty(value) -> bool:
    """Return True if value is a meaningful, non-empty note."""
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


def inherit_group_notes(
    df: pd.DataFrame,
    path_col: str = "hierarchy_path",
    note_col: str = "group_notes_value",
    out_col: str = "group_notes_inherited",
) -> pd.DataFrame:
    """
    Inherit `group_notes_value` from the *nearest previous parent* in the hierarchy.

    Forward-only logic:
      - Iterate rows from top to bottom.
      - Maintain a map: seen_path -> note for rows that have their own non-empty note.
      - For the current row with path P:
          * Look for nearest ancestor among paths already seen:
              P[:-1], P[:-2], ... until empty.
          * If current row has no own note, inherit that ancestor's note.
      - Only rows that have their own note are added to the map
        (purely inherited rows do NOT become new parents).

    Also reorders columns so they appear as:
        ... note_col, out_col, ...
    """

    df = df.copy()

    # Normalize hierarchy_path into tuples
    norm_paths = []
    for val in df[path_col]:
        norm_paths.append(_parse_path_cell(val))
    df[path_col] = norm_paths

    # Map from path -> own group note (from previous rows only)
    parent_note_map = {}

    inherited_notes = []

    for _, row in df.iterrows():
        path = row.get(path_col)
        own_note = row.get(note_col)

        # 1. Find nearest previous ancestor note
        inherited_note = None
        if isinstance(path, tuple):
            cur = path[:-1]  # start from immediate parent
            while cur:
                if cur in parent_note_map:
                    inherited_note = parent_note_map[cur]
                    break
                cur = cur[:-1]

        # 2. Decide final note for this row
        final_note = own_note if _is_non_empty(own_note) else inherited_note
        inherited_notes.append(final_note)

        # 3. Update map for future rows *only if* this row has its own note
        if isinstance(path, tuple) and _is_non_empty(own_note):
            parent_note_map[path] = own_note

    df[out_col] = inherited_notes

    # 4. Reorder columns: group_notes_value, group_notes_inherited
    cols = list(df.columns)

    if note_col in cols and out_col in cols:
        cols.remove(out_col)
        idx = cols.index(note_col)
        cols.insert(idx + 1, out_col)
        df = df[cols]

    return df
