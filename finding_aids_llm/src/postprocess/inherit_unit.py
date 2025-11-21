# src/postprocess/inherit_unit.py

import pandas as pd


def _is_non_empty(value) -> bool:
    """Return True if value is a meaningful, non-empty unit."""
    if value is None:
        return False
    s = str(value).strip()
    if s == "" or s.lower() == "nan":
        return False
    return True


def inherit_unit(
    df: pd.DataFrame,
    unit_col: str = "unit_value",
    out_col: str = "unit_value_inherited",
) -> pd.DataFrame:
    """
    Forward-only inheritance for unit values.

    For each row from top to bottom:
      - If `unit_value` is non-empty, that becomes the new current unit.
      - If `unit_value` is empty, it inherits the most recent non-empty unit
        from a previous row.
      - No grouping, no path involved: purely vertical propagation.

    Adds `out_col` and places it immediately after `unit_col`.
    """
    df = df.copy()

    current_unit = None
    inherited_units = []

    for _, row in df.iterrows():
        own_unit = row.get(unit_col)

        if _is_non_empty(own_unit):
            current_unit = own_unit
            inherited_units.append(own_unit)
        else:
            inherited_units.append(current_unit)

    df[out_col] = inherited_units

    # Reorder columns: unit_value, unit_value_inherited
    cols = list(df.columns)
    if unit_col in cols and out_col in cols:
        cols.remove(out_col)
        idx = cols.index(unit_col)
        cols.insert(idx + 1, out_col)
        df = df[cols]

    return df
