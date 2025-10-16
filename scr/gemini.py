#!/usr/bin/env python3
"""
Finding aid PDF → JSON (hierarchical) → XLSX (flat).

- Uses ONLY the official google-genai client:
    from google import genai
    from google.genai import types
- Uploads each page-chunk as an in-memory mini-PDF (PdfWriter → BytesIO → Part.from_bytes).
- Supports --pages N or N-M to process a subset of a large PDF.
- Shows progress with tqdm.
- Robust JSON parsing so a single malformed chunk won't crash the run.
- Captures series-level notes into Series_Notes (not duplicated in item Text).

XLSX columns:
  Unit, Finding_Aid_Reference, Series, Series_Notes, Title, Text, Dates, Item_Annotations, Hierarchy_Path
"""

from __future__ import annotations
import argparse
import io
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from pypdf import PdfReader, PdfWriter
from tqdm import tqdm

from google import genai
from google.genai import types


# -------- Prompt (SCOPE + RULES + STRUCTURE) --------
PROMPT_JSON_FIRST = r"""
You are converting a typed archival finding aid (1960s–1990s) into a hierarchical JSON.

SCOPE
- Ignore the "context area" at the front (repository banners, page headers like “Miscellaneous Letters”, cover matter).
- Parse ONLY the hierarchical record list (series/groups and their items).
- Capture handwritten/digital annotations that appear in the record list.

DEFINITIONS & STRUCTURE
- A Series is the parent-level heading above a block of items (often a person/firm name). When a new parent heading appears, that becomes the current series; following items inherit it until the next parent heading.
- Page/collection headers (e.g., “Miscellaneous Letters”) are NOT series. Put such page-level context in "document_notes" only.
- Series notes: If a "Note:" line appears immediately under a series heading (applies to that whole series), capture it verbatim as series_notes for that series. Do NOT duplicate this note inside any item text.
- “Unit n” lines (e.g., Unit 1, Unit 22) set the current unit; all subsequent items inherit that unit until another “Unit n” appears.
- Finding_Aid_Reference is the original left-margin numbering EXACTLY AS PRINTED (e.g., "1.", "2.", "5.", "5.(1)", "5.(2)", "5/1").
  - If a sub-item appears only as "(1)" under a top-level "5.", emit "5.(1)" (or "5/1" if that page uses slash style). Preserve whatever style the page uses.
  - Do NOT normalize to "5.1" or strip trailing dots/parentheses/slashes.
- Title is the item’s first sentence/label (e.g., "Letter.", "Bond.", "Mortgage.", "Grant by Purchase."). Do NOT include the series/heading itself in Title.
- Text is the FULL item content as one string, INCLUDING the Title, the Dates line, any “x sheet(s).”/extent lines (even if OCR-spaced oddly), and any "Note:" lines. Do NOT include explicit "Unit n" lines in Text.
- Dates is the verbatim date string from the item (use the clearest/last explicit date line). Do not infer or reformat dates.
- annotations are item-level notes (e.g., "Note: …"). These must ALSO be present inline within Text (except the series-level note captured in series_notes).

RULES
- Preserve punctuation and case exactly.
- Remove line breaks unless they indicate a new row/item; keep whitespace minimal (single spaces between words).
- If a field is missing, use "" (empty string), not null.
- Word-level OCR uncertainty:
  - When ANY word/token is not confidently read, insert an inline tag immediately after the best-guess word in this exact form:
    <best_guess>[OCR uncertain <raw_or_alt>, uncertain level NN/100]
    - Example: "return to Melbourne[OCR uncertain Melboume, uncertain level 63/100]".
  - Place the bracket before trailing punctuation if present (e.g., "Bond[OCR uncertain Boud, uncertain level 58/100].")
- Do not infer or reformat dates; keep as seen (e.g., "c.1900–1910").
- Do not normalize or pad numbering (keep "1/1", "1/1/1", "5.(1)" verbatim).
- Never return prose. ALWAYS return valid JSON only.
- If these pages contain no items, return exactly:
{"series": [], "unassigned_items": [], "document_notes": "no items on these pages"}

OUTPUT (return ONLY JSON, no prose):
{
  "series": [
    {
      "series": "<parent heading text or ''>",
      "series_notes": "<verbatim 'Note:' directly under the series heading or ''>",
      "items": [
        {
          "unit": "<Unit n or ''>",
          "finding_aid_reference": "<left margin number as printed>",
          "title": "<first-sentence label or ''>",
          "text": "<FULL item text (includes title + dates + sheets + notes; excludes series-level note)>",
          "dates": "<verbatim date or ''>",
          "annotations": ["<item-level note>", "..."]
        }
      ]
    }
  ],
  "unassigned_items": [],
  "document_notes": "<page/collection headers or OCR caveats; NOT series>"
}
"""


# --------------------- JSON helpers ---------------------
_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE)

def extract_fenced_json(text: str) -> Dict[str, Any]:
    if not text:
        raise ValueError("Empty model output")
    m = _JSON_FENCE.search(text)
    candidate = None
    if m:
        candidate = m.group(1)
    else:
        b0, b1 = text.find("{"), text.rfind("}")
        if b0 != -1 and b1 != -1 and b1 > b0:
            candidate = text[b0:b1+1]
    if not candidate:
        raise ValueError("No JSON object found in model output")
    try:
        return json.loads(candidate)
    except Exception:
        compact = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", candidate)
        return json.loads(compact)

def try_parse_json_block(text: str) -> Optional[Dict[str, Any]]:
    """Robust extractor: fences → raw → slice first '{'..last '}' (control-char scrub)."""
    if not text:
        return None
    t = (text or "").strip()
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", t)

    # fenced
    try:
        return extract_fenced_json(t)
    except Exception:
        pass
    # raw
    try:
        return json.loads(t)
    except Exception:
        pass
    # slice
    b0, b1 = t.find("{"), t.rfind("}")
    if b0 != -1 and b1 != -1 and b1 > b0:
        slice_ = t[b0:b1+1]
        slice_ = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", slice_)
        try:
            return json.loads(slice_)
        except Exception:
            return None
    return None


# --------------------- Merge → hierarchical ---------------------
def _safe(x: Any) -> str:
    return "" if x is None else str(x)

def merge_model_json(parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {"series": [], "unassigned_items": [], "document_notes": ""}

    for part in parts:
        # notes
        dn = _safe(part.get("document_notes"))
        if dn:
            merged["document_notes"] = (merged["document_notes"] + " | " + dn).strip(" |") if merged["document_notes"] else dn

        # unassigned
        merged["unassigned_items"].extend(part.get("unassigned_items", []) or [])

        # series blocks
        for sb in (part.get("series") or []):
            sname = _safe(sb.get("series"))
            snotes = _safe(sb.get("series_notes"))
            items = list(sb.get("items") or [])
            # merge consecutive identical series names (carry forward notes if present)
            if merged["series"] and _safe(merged["series"][-1].get("series")) == sname:
                if snotes and not _safe(merged["series"][-1].get("series_notes")):
                    merged["series"][-1]["series_notes"] = snotes
                merged["series"][-1]["items"].extend(items)
            else:
                merged["series"].append({"series": sname, "series_notes": snotes, "items": items})
    return merged


# --------------------- Flatten → rows ---------------------
def _flatten_json_to_rows(obj: Dict[str, Any]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    def push(series_name: str, series_notes: str, it: Dict[str, Any]):
        rows.append({
            "Unit": _safe(it.get("unit")).strip(),
            "Finding_Aid_Reference": _safe(it.get("finding_aid_reference")).strip(),
            "Series": _safe(series_name).strip(),
            "Series_Notes": _safe(series_notes).strip(),
            "Title": _safe(it.get("title")).strip(),
            "Text": _safe(it.get("text")).strip(),
            "Dates": _safe(it.get("dates")).strip(),
            "Item_Annotations": "; ".join(
                [_safe(a).strip() for a in (it.get("annotations") or []) if _safe(a).strip()]
            ),
            "Hierarchy_Path": _safe(it.get("finding_aid_reference")).strip(),
        })

    for sb in (obj.get("series") or []):
        sname = _safe(sb.get("series"))
        snotes = _safe(sb.get("series_notes"))
        for it in (sb.get("items") or []):
            push(sname, snotes, it)

    for it in (obj.get("unassigned_items") or []):
        push("", "", it)

    return rows

def _repair_finding_aid_reference(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    If a subitem appears as bare "(n)" or "n" after a top-level "5.", emit "5.(n)" (or "5/n" if slash style detected).
    """
    out: List[Dict[str, str]] = []
    top = ""     # e.g., "5."
    style = "paren"
    for r in rows:
        ref = (r.get("Finding_Aid_Reference") or "").strip()
        if re.match(r"^\d+\.\s*$", ref):
            top = ref
        else:
            m_bare = re.match(r"^\(?([0-9]+)\)?\s*$", ref)
            if m_bare and top:
                r["Finding_Aid_Reference"] = (
                    f"{top.rstrip('.').strip()}/{m_bare.group(1)}" if style == "slash" else f"{top}({m_bare.group(1)})"
                )
        if re.match(r"^\d+\.\(\d+\)$", ref):
            style = "paren"
        elif re.match(r"^\d+/\d+$", ref):
            style = "slash"
        out.append(r)
    return out

def _fill_forward_units(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    cur = ""
    for r in rows:
        u = (r.get("Unit") or "").strip()
        if u:
            cur = u
        else:
            r["Unit"] = cur
    return rows

def _remove_series_note_from_text(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    If the model still echoed a series-level note inside the item's Text, strip it
    only when it exactly matches the Series_Notes prefix.
    """
    cleaned: List[Dict[str, str]] = []
    for r in rows:
        sn = (r.get("Series_Notes") or "").strip()
        txt = (r.get("Text") or "")
        if sn and txt.startswith(sn):
            t = txt[len(sn):].lstrip(" \n\r\t")
            r = dict(r)
            r["Text"] = t
        cleaned.append(r)
    return cleaned


# --------------------- Writers ---------------------
def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def write_xlsx(path: Path, rows: List[Dict[str, str]]) -> None:
    cols = [
        "Unit",
        "Finding_Aid_Reference",
        "Series",
        "Series_Notes",
        "Title",
        "Text",
        "Dates",
        "Item_Annotations",
        "Hierarchy_Path",
    ]
    df = pd.DataFrame(rows, columns=cols)
    # force text to avoid Excel auto-formatting
    df = df.astype({c: "string" for c in cols})
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Records")
        wb = writer.book
        ws = writer.sheets["Records"]
        text_fmt = wb.add_format({"num_format": "@"})
        for col_idx, _ in enumerate(cols):
            ws.set_column(col_idx, col_idx, 28, text_fmt)
        ws.freeze_panes(1, 0)


# --------------------- Page range helpers ---------------------
def _parse_pages_arg(pages_arg: Optional[str], total: int) -> Tuple[int, int]:
    if not pages_arg:
        return (1, total)
    s = pages_arg.strip()
    m1 = re.match(r"^(\d+)$", s)
    if m1:
        n = max(1, min(int(m1.group(1)), total))
        return (n, n)
    m2 = re.match(r"^(\d+)-(\d+)$", s)
    if m2:
        a, b = int(m2.group(1)), int(m2.group(2))
        if b < a:
            a, b = b, a
        a = max(1, min(a, total))
        b = max(1, min(b, total))
        return (a, b)
    raise ValueError("--pages must be N or N-M (1-based)")

def _chunk_ranges(a: int, b: int, size: int) -> List[Tuple[int, int]]:
    if size <= 0:
        return [(a, b)]
    out: List[Tuple[int, int]] = []
    s = a
    while s <= b:
        e = min(b, s + size - 1)
        out.append((s, e))
        s = e + 1
    return out


# --------------------- Main pipeline ---------------------
def run(pdf_path: Path,
        out_json: Path,
        out_xlsx: Path,
        model_name: str,
        temperature: float,
        pages_per_chunk: int,
        pages: Optional[str] = None) -> None:

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")

    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    if total_pages == 0:
        raise RuntimeError("PDF has 0 pages")

    # compute selection and ranges
    a0, b0 = _parse_pages_arg(pages, total_pages)
    ranges = _chunk_ranges(a0, b0, pages_per_chunk)

    parts: List[Dict[str, Any]] = []
    failed: List[Tuple[int, int, str]] = []

    for a, b in tqdm(ranges, desc="Parsing page chunks", unit="chunk"):
        # Build mini-PDF (in memory)
        w = PdfWriter()
        for p in range(a - 1, b):  # 1-based → 0-based
            w.add_page(reader.pages[p])
        bio = io.BytesIO()
        w.write(bio)

        pdf_part = types.Part.from_bytes(data=bio.getvalue(), mime_type="application/pdf")
        try:
            prompt_part = types.Part.from_text(text=PROMPT_JSON_FIRST)
        except TypeError:
            prompt_part = types.Part(text=PROMPT_JSON_FIRST)

        user_content = types.Content(role="user", parts=[pdf_part, prompt_part])

        # Call model with a tiny retry to survive transient failures
        resp = None
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=[user_content],
                    generation_config=types.GenerateContentConfig(
                        temperature=temperature,
                        response_mime_type="application/json",
                    ),
                )
                break
            except TypeError:
                # older genai without GenerateContentConfig
                resp = client.models.generate_content(
                    model=model_name,
                    contents=[user_content],
                )
                break
            except Exception:
                if attempt == 2:
                    resp = None
                else:
                    time.sleep(2 * (attempt + 1))
        if resp is None:
            failed.append((a, b, "request_failed"))
            Path(f"{out_json}.chunk_{a}-{b}.err.txt").write_text("request failed", encoding="utf-8")
            continue

        # Extract text
        text = getattr(resp, "text", "") or ""
        if not text.strip():
            # stitch from first candidate if available
            try:
                cand = (resp.candidates or [])[0]
                parts_ = getattr(cand, "content", {}).parts or []
                text = "".join(getattr(pt, "text", "") for pt in parts_ if hasattr(pt, "text"))
            except Exception:
                text = ""
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text or "")

        # Parse JSON robustly
        obj = try_parse_json_block(text)
        if obj is None:
            failed.append((a, b, "non_json"))
            Path(f"{out_json}.chunk_{a}-{b}.txt").write_text(text, encoding="utf-8")
            print(f"[warn] Non-JSON for pages {a}-{b}; wrote {out_json}.chunk_{a}-{b}.txt")
            continue

        parts.append(obj)

        # rolling partial (handy for very long runs)
        try:
            Path(f"{out_json}.partial").write_text(
                json.dumps({"chunks": parts}, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    if not parts:
        raise RuntimeError("No chunks produced valid JSON. See *.chunk_*.txt for raw outputs.")

    # Merge → hierarchical
    merged = merge_model_json(parts)

    # Flatten → rows
    rows = _flatten_json_to_rows(merged)
    rows = _repair_finding_aid_reference(rows)
    rows = _fill_forward_units(rows)
    rows = _remove_series_note_from_text(rows)

    # Write outputs
    write_json(out_json, merged)
    write_xlsx(out_xlsx, rows)

    if failed:
        print(f"[done] {len(parts)} chunks succeeded, {len(failed)} failed.")
        for a, b, why in failed:
            print(f"  - pages {a}-{b}: {why} (see sidecar files)")


def main():
    p = argparse.ArgumentParser(description="Finding aid PDF → JSON (hierarchical) → XLSX (flat).")

    p.add_argument("--pdf", required=True, help="Path to the finding aid PDF.")
    p.add_argument("--out_json", required=True, help="Path to save the raw JSON (from model).")
    p.add_argument("--out_xlsx", required=True, help="Path to save the flattened Excel file.")
    p.add_argument("--model_name", default="models/gemini-2.5-flash", help="Model ID.")
    p.add_argument("--temperature", type=float, default=0.3)
    p.add_argument("--pages_per_chunk", type=int, default=5)
    p.add_argument("--pages", type=str, default=None, help="Optional page range N or N-M (1-based) to limit processing.")

    args = p.parse_args()

    pdf_path = Path(args.pdf)
    out_json = Path(args.out_json)
    out_xlsx = Path(args.out_xlsx)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    run(pdf_path, out_json, out_xlsx, args.model_name, args.temperature, args.pages_per_chunk, args.pages)
    print(f"JSON written: {out_json}")
    print(f"XLSX written: {out_xlsx}")


if __name__ == "__main__":
    main()
