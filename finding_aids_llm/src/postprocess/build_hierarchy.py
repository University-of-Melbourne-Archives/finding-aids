import argparse
import pandas as pd
import re
from inherit_group import inherit_group_notes
from inherit_series import inherit_series
from inherit_unit import inherit_unit


import re

def parse_parent(ref: str):
    """
    Parse parent-style finding-aid references into (path_tuple, root_tuple).

    Handles:
      - Slash paths with optional dots: "2/1", "2/1.", "2./1", "10./4./7."
      - Composite: "6.(1)", "101. (1)", "101(1)"
      - Fuzzy numeric parents: "106.?", "102.", "25", "25."
    """
    if ref is None:
        return None

    s = str(ref).strip()
    if s == "" or s.lower() == "nan":
        return None

    # Remove stray quotes like "26.
    s = s.replace('"', "").replace("'", "").strip()
    if s == "":
        return None

    # (1) Slash paths: 2/1, 2/1., 2./1, 2./1., 10./4./7.
    if re.fullmatch(r"\d+\.?(?:/\d+\.?)+\.?", s):
        s_clean = s.rstrip(".")
        parts = [p.rstrip(".") for p in s_clean.split("/")]
        nums = tuple(int(p) for p in parts)
        return nums, nums  # children attach under full path

    # (2) Composite: 6.(1), 101.(1), 101. (1), 101(1)
    m = re.fullmatch(r"(\d+)\.?\s*\((\d+)\)", s)
    if m:
        parent = int(m.group(1))
        child = int(m.group(2))
        path = (parent, child)
        root = (parent,)  # children "(2)" attach under (parent,)
        return path, root

    # (3) Fuzzy numeric parent: "106.?", "102.", "25", "25."
    # Condition: starts with digits, and no slash or "(" in the string
    if "/" not in s and "(" not in s:
        m = re.match(r"(\d+)", s)
        if m:
            n = int(m.group(1))
            path = (n,)
            return path, path

    return None




def parse_child(ref: str):
    """
    Parse child reference of the form "(n)" -> int(n), else None.
    """
    if ref is None:
        return None
    s = str(ref).strip()
    if re.fullmatch(r"\(\d+\)", s):
        return int(s[1:-1])
    return None


def compute_hierarchy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a dataframe with at least columns:
      - 'finding_aid_reference_raw_value'
      - 'group_value'
    compute the 'hierarchy_path' column (tuple of ints or None).

    Logic:
      1. Try to parse finding_aid_reference_raw_value as parent.
      2. Else, try to parse as child "(n)" and attach to last_root.
      3. If still None and group_value is a pure integer string, use (int(group_value),).
    """
    hierarchy_paths = []
    last_root = None  # numeric tuple used for attaching children like "(4)"

    for _, row in df.iterrows():
        ref_raw = row.get("finding_aid_reference_raw_value")
        group_val = row.get("group_value")

        numeric_path = None

        # 1) Parent-style reference?
        parent_info = parse_parent(ref_raw)
        if parent_info is not None:
            path, root = parent_info
            numeric_path = path
            last_root = root  # update parent root context for children

        else:
            # 2) Child-style reference "(n)"?
            child_num = parse_child(ref_raw)
            if child_num is not None:
                if last_root is not None:
                    numeric_path = last_root + (child_num,)
                else:
                    numeric_path = (child_num,)

        # 3) Fallback to group_value if no numeric_path yet
        if numeric_path is None and group_val is not None:
            sgv = str(group_val).strip()
            if sgv.isdigit():
                numeric_path = (int(sgv),)

        hierarchy_paths.append(numeric_path)

    df["hierarchy_path"] = hierarchy_paths
    return df


def postprocess_and_save(df: pd.DataFrame, out_path: str, as_csv: bool = False):
    """
    Remove *confidence columns, move hierarchy_path after finding_aid_reference_raw_value,
    and save to the given path (XLSX or CSV).
    """
    # 1) Drop all '*confidence' columns
    confidence_cols = [c for c in df.columns if c.endswith("confidence")]
    if confidence_cols:
        df = df.drop(columns=confidence_cols)

    # 2) Move 'hierarchy_path' right after 'finding_aid_reference_raw_value'
    cols = list(df.columns)
    if "hierarchy_path" in cols and "finding_aid_reference_raw_value" in cols:
        cols.remove("hierarchy_path")
        ref_idx = cols.index("finding_aid_reference_raw_value")
        cols.insert(ref_idx + 1, "hierarchy_path")
        df = df[cols]

    # 3) Save
    if as_csv:
        df.to_csv(out_path, index=False)
    else:
        df.to_excel(out_path, index=False)
    print(f"[✓] hierarchy_path added and saved to: {out_path}")


def build_hierarchy_xlsx(input_xlsx: str, out_xlsx: str):
    # Read everything as string
    df = pd.read_excel(input_xlsx, dtype=str)
    df = compute_hierarchy(df)
    df = inherit_group_notes(
        df,
        path_col="hierarchy_path",
        note_col="group_notes_value",
        out_col="group_notes_inherited",  # or "group_notes_value" if you want to overwrite
    )
    # Inherit series info from nearest parent
    df = inherit_series(
        df,
        path_col="hierarchy_path",
        series_col="series_value",
        series_note_col="series_notes_value",
        out_series_col="series_value_inherited",  # or "series_value" to overwrite
        out_series_note_col="series_notes_inherited",  # or "series_notes_value"
    )
    df = inherit_unit(
        df,
        unit_col="unit_value",
        out_col="unit_value_inherited",
    )
    postprocess_and_save(df, out_xlsx, as_csv=False)


def build_hierarchy_csv(input_csv: str, out_csv: str):
    # Read everything as string
    df = pd.read_csv(input_csv, dtype=str)
    df = compute_hierarchy(df)
    df = inherit_group_notes(
        df,
        path_col="hierarchy_path",
        note_col="group_notes_value",
        out_col="group_notes_inherited",  # or "group_notes_value" if you want to overwrite
    )
    # Inherit series info from nearest parent
    df = inherit_series(
        df,
        path_col="hierarchy_path",
        series_col="series_value",
        series_note_col="series_notes_value",
        out_series_col="series_value_inherited",  # or "series_value" to overwrite
        out_series_note_col="series_notes_inherited",  # or "series_notes_value"
    )
    df = inherit_unit(
        df,
        unit_col="unit_value",
        out_col="unit_value_inherited",
    )
    postprocess_and_save(df, out_csv, as_csv=True)


def main():
    parser = argparse.ArgumentParser(description="Build hierarchy_path for finding aids.")
    parser.add_argument("--input_xlsx", help="Path to input XLSX file")
    parser.add_argument("--out_xlsx", help="Path to output XLSX file")
    parser.add_argument("--input_csv", help="Path to input CSV file")
    parser.add_argument("--out_csv", help="Path to output CSV file")
    args = parser.parse_args()

    # Decide mode: XLSX or CSV
    if args.input_xlsx and args.out_xlsx:
        build_hierarchy_xlsx(args.input_xlsx, args.out_xlsx)
    elif args.input_csv and args.out_csv:
        build_hierarchy_csv(args.input_csv, args.out_csv)
    else:
        raise SystemExit(
            "You must provide either --input_xlsx and --out_xlsx, "
            "or --input_csv and --out_csv."
        )


if __name__ == "__main__":
    main()
