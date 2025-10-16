#!/usr/bin/env python3
"""
Finding aid PDF → JSON (hierarchical) → XLSX (flat) via Mistral Vision (Files API).
- Renders PDF pages to images
- Uploads images to Mistral Files API
- Sends prompt + one file chunk per image
- Parses strict JSON
- Fault tolerant: logs bad chunks to sidecar NDJSON and continues

XLSX columns:
  Unit, Finding_Aid_Reference, Series, Title, Text, Dates, Item_Annotations, Hierarchy_Path
"""

from __future__ import annotations
import argparse
import io
import json
import os
import re
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import base64
import pandas as pd
from tqdm import tqdm
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from PIL import Image
from mistralai import Mistral



# --------------------- Prompt (your original) ---------------------
PROMPT_JSON_FIRST = r"""
You are converting a typed archival finding aid (1960s–1990s) into a hierarchical JSON.

SCOPE
- Ignore the "context area" at the front (repository banners, page headers like “Miscellaneous Letters”, cover matter).
- Parse ONLY the hierarchical record list (series/groups and their items).
- Capture handwritten/digital annotations that appear in the record list.

DEFINITIONS & STRUCTURE
- A Series is the parent-level heading above a block of items (often a person/firm name). When a new parent heading appears, that becomes the current series; following items inherit it until the next parent heading.
- Page/collection headers (e.g., “Miscellaneous Letters”) are NOT series. Put such page-level context in "document_notes" only.
- “Unit n” lines (e.g., Unit 1, Unit 22) set the current unit; all subsequent items inherit that unit until another “Unit n” appears.
- Finding_Aid_Reference is the original left-margin numbering EXACTLY AS PRINTED (e.g., "1.", "2.", "5.", "5.(1)", "5.(2)", "5/1").
  - If a sub-item appears only as "(1)" under a top-level "5.", emit "5.(1)" (or "5/1" if that page uses slash style). Preserve whatever style the page uses.
  - Do NOT normalize to "5.1" or strip trailing dots/parentheses/slashes.
- Title is the item’s first sentence/label (e.g., "Letter.", "Bond.", "Mortgage.", "Grant by Purchase."). Do NOT include the series/heading itself in Title.
- Text is the FULL item content as one string, INCLUDING the Title, the Dates line, any “x sheet(s).”/extent lines (even if OCR-spaced oddly), and any "Note:" lines. Do NOT include explicit "Unit n" lines in Text.
- Dates is the verbatim date string from the item (use the clearest/last explicit date line). Do not infer or reformat dates.
- annotations are item-level notes (e.g., "Note: …"). These must ALSO be present inline within Text.

RULES
- Preserve punctuation and case exactly.
- Remove line breaks unless they indicate a new row/item; keep whitespace minimal (single spaces between words).
- If a field is missing, use "" (empty string), not null.
- Word-level OCR uncertainty:
  - When ANY word/token is not confidently read, insert an inline tag immediately after the best-guess word in this exact form:
    <best_guess>[OCR uncertain <raw_or_alt>, uncertain level NN/100]
    - Example: "return to Melbourne[OCR uncertain Melboume, uncertain level 63/100]".
  - Use NN = your 0–100 confidence estimate (higher = more confident). Tag each uncertain word once.
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
      "items": [
        {
          "unit": "<Unit n or ''>",
          "finding_aid_reference": "<left margin number as printed>",
          "title": "<first-sentence label or ''>",
          "text": "<FULL item text (includes title + dates + sheets + notes)>",
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

# --------------------- Config ---------------------
@dataclass
class LLMConfig:
    model_name: str = "pixtral-12b-latest"  # vision model
    temperature: float = 0.3
    max_output_tokens: int = 4096

# --------------------- JSON helpers & sidecar ---------------------
_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE)

def try_parse_json(raw: str) -> Dict[str, Any]:
    # 1) direct
    try:
        return json.loads(raw)
    except Exception:
        pass
    # 2) fenced
    m = _JSON_FENCE.search(raw or "")
    if m:
        return json.loads(m.group(1))
    # 3) first '{' .. last '}'
    if raw:
        b0, b1 = raw.find("{"), raw.rfind("}")
        if b0 != -1 and b1 > b0:
            return json.loads(raw[b0:b1+1])
    raise ValueError("No valid JSON object detected")

def log_parse_failure(sidecar_path: Path, chunk_start: int, chunk_end: int, raw: str, err: Exception) -> None:
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": int(time.time()),
        "chunk_start": chunk_start,
        "chunk_end": chunk_end,
        "error": f"{type(err).__name__}: {err}",
        "trace": "".join(traceback.format_exc()),
        "raw": (raw or "")[:20000],
    }
    with open(sidecar_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

# --------------------- Post-processing (unchanged from your script) ---------------------
def _safe(x: Any) -> str:
    return "" if x is None else str(x).strip()

def split_title_if_missing(row: Dict[str, str]) -> Dict[str, str]:
    if _safe(row.get("Title")):
        return row
    txt = _safe(row.get("Text"))
    m = re.match(r"^(.{1,80}?\.)\s+(.*)$", txt)
    if m:
        row["Title"] = m.group(1).strip()
        row["Text"] = txt
    return row

def fill_forward_units(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    current = ""
    for r in rows:
        u = _safe(r.get("Unit"))
        if u:
            current = u
        else:
            r["Unit"] = current
    return rows

def repair_finding_aid_reference(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    top = ""         # e.g., "5."
    style = "paren"  # learn 'slash' if we encounter 'N/k'
    for r in rows:
        ref = _safe(r.get("Finding_Aid_Reference"))
        if re.match(r"^\d+\.\s*$", ref):
            top = ref
        else:
            m_bare = re.match(r"^\(?([0-9]+)\)?\s*$", ref)
            if m_bare and top:
                ref = f"{top.rstrip('.').strip()}/{m_bare.group(1)}" if style == "slash" else f"{top}({m_bare.group(1)})"
                r["Finding_Aid_Reference"] = ref
        if re.match(r"^\d+\.\(\d+\)$", ref):
            style = "paren"
        elif re.match(r"^\d+/\d+$", ref):
            style = "slash"
        out.append(r)
    return out

def flatten_model_json(model_json: Dict[str, Any]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for sb in (model_json or {}).get("series", []):
        series_name = _safe(sb.get("series"))
        for it in sb.get("items", []):
            rows.append({
                "Unit": _safe(it.get("unit")),
                "Finding_Aid_Reference": _safe(it.get("finding_aid_reference")),
                "Series": series_name,
                "Title": _safe(it.get("title")),
                "Text": _safe(it.get("text")),
                "Dates": _safe(it.get("dates")),
                "Item_Annotations": "; ".join([_safe(a) for a in it.get("annotations", []) if _safe(a)]),
                "Hierarchy_Path": _safe(it.get("finding_aid_reference")),
            })
    rows = [split_title_if_missing(r) for r in rows]
    rows = repair_finding_aid_reference(rows)
    rows = fill_forward_units(rows)
    return rows

def merge_model_json(parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {"series": [], "unassigned_items": [], "document_notes": ""}
    for part in parts:
        dn = _safe(part.get("document_notes"))
        if dn:
            merged["document_notes"] = (merged["document_notes"] + " | " + dn).strip(" |") if merged["document_notes"] else dn
        merged["unassigned_items"].extend(part.get("unassigned_items", []))
        for sb in part.get("series", []):
            sname = _safe(sb.get("series"))
            items = sb.get("items", []) or []
            if merged["series"] and _safe(merged["series"][-1].get("series")) == sname:
                merged["series"][-1]["items"].extend(items)
            else:
                merged["series"].append({"series": sname, "items": list(items)})
    return merged

def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def write_xlsx(path: Path, rows: List[Dict[str, str]]) -> None:
    cols = [
        "Unit",
        "Finding_Aid_Reference",
        "Series",
        "Title",
        "Text",
        "Dates",
        "Item_Annotations",
        "Hierarchy_Path",
    ]
    df = pd.DataFrame(rows, columns=cols)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)

# --------------------- PDF → images for a chunk ---------------------
def render_pdf_chunk_to_images(pdf_path: Path, start_page_1based: int, end_page_1based: int, dpi: int = 300) -> List[Image.Image]:
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    for p in range(start_page_1based - 1, end_page_1based):
        writer.add_page(reader.pages[p])
    bio = io.BytesIO()
    writer.write(bio)
    pdf_bytes = bio.getvalue()
    return convert_from_bytes(pdf_bytes, dpi=dpi)  # -> List[PIL.Image]

# --------------------- Mistral Vision client using Files API ---------------------
class MistralVisionClient:
    def __init__(self, api_key: Optional[str], cfg: LLMConfig):
        self.client = Mistral(api_key=api_key or os.getenv("MISTRAL_API_KEY", ""))
        if not (api_key or os.getenv("MISTRAL_API_KEY")):
            raise RuntimeError("Missing Mistral API key (pass --api_key or set MISTRAL_API_KEY).")
        self.cfg = cfg

    @staticmethod
    def _pil_to_data_uri(img: Image.Image) -> str:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    def complete_json(self, prompt_text: str, pil_images: List[Image.Image]) -> Dict[str, Any]:
        """
        Works with mistralai 1.9.9:
        - first user message is plain text (string)
        - then one user message per image with a single image_url chunk (data URI)
        """
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": "You are a careful OCR + structuring assistant."},
            {"role": "user", "content": prompt_text},  # plain string
        ]
        for img in pil_images:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": self._pil_to_data_uri(img)}
                ],
            })

        resp = self.client.chat.complete(
            model=self.cfg.model_name,
            messages=messages,
            temperature=self.cfg.temperature,
            response_format={"type": "json_object"},
            max_tokens=self.cfg.max_output_tokens,
        )
        raw = resp.choices[0].message.content
        return try_parse_json(raw)



# --------------------- Main flow ---------------------
def count_pages(pdf_path: Path) -> int:
    r = PdfReader(str(pdf_path))
    return len(r.pages)

def chunk_ranges(total_pages: int, size: int) -> List[Tuple[int, int]]:
    if size <= 0:
        return [(1, total_pages)]
    out = []
    s = 1
    while s <= total_pages:
        e = min(total_pages, s + size - 1)
        out.append((s, e))
        s = e + 1
    return out

def run(pdf_path: Path, out_json: Path, out_xlsx: Path,api_key: Optional[str], model_name: str,temperature: float, pages_per_chunk: int,pages: Optional[str]) -> None:

    cfg = LLMConfig(model_name=model_name, temperature=temperature, max_output_tokens=4096)
    mv = MistralVisionClient(api_key=api_key, cfg=cfg)

    total_pages = count_pages(pdf_path)

    # If --pages specified, restrict
    if pages:
        if "-" in pages:
            start, end = pages.split("-", 1)
            start, end = int(start), int(end)
        else:
            start = end = int(pages)
        # clamp to total_pages
        start = max(1, start)
        end = min(total_pages, end)
        ranges = chunk_ranges(end - start + 1, pages_per_chunk)
        # shift ranges to the actual start offset
        ranges = [(r[0] + start - 1, r[1] + start - 1) for r in ranges]
    else:
        ranges = chunk_ranges(total_pages, pages_per_chunk)


    parts: List[Dict[str, Any]] = []
    sidecar = out_json.with_suffix(out_json.suffix + ".errors.ndjson")

    for a, b in tqdm(ranges, desc="Parsing page chunks", unit="chunk"):
        try:
            pil_images = render_pdf_chunk_to_images(pdf_path, a, b, dpi=300)
            try:
                js = mv.complete_json(PROMPT_JSON_FIRST, pil_images)  # returns dict
                parts.append(js)
            except Exception as pe:
                log_parse_failure(sidecar, a, b, "", pe)
                print(f"[warn] Chunk {a}-{b}: {pe}; recorded to {sidecar.name}")
                continue
        except Exception as e:
            log_parse_failure(sidecar, a, b, "[no raw; upstream error]", e)
            print(f"[warn] Chunk {a}-{b}: upstream error; recorded to {sidecar.name}")
            continue

    if not parts:
        print("[warn] No chunks succeeded. Writing empty scaffold.")
        merged = {"series": [], "unassigned_items": [], "document_notes": "no items on these pages"}
    else:
        merged = merge_model_json(parts)

    rows = flatten_model_json(merged)
    write_json(out_json, merged)
    write_xlsx(out_xlsx, rows)

def main():
    p = argparse.ArgumentParser(description="Finding aid PDF → JSON → XLSX via Mistral Vision (Files API, fault-tolerant).")
    p.add_argument("--pdf", required=True, help="Path to the finding aid PDF.")
    p.add_argument("--out_json", required=True, help="Path to save the raw merged JSON (from model).")
    p.add_argument("--out_xlsx", required=True, help="Path to save the flattened Excel file.")
    p.add_argument("--api_key", type=str, default="", help="API key for Mistral (falls back to MISTRAL_API_KEY).")
    p.add_argument("--model_name", type=str, default="pixtral-12b-latest", help="Mistral model (vision).")
    p.add_argument("--temperature", type=float, default=0.3)
    p.add_argument("--pages_per_chunk", type=int, default=5)
    p.add_argument("--pages", type=str, default=None, help="Optional page range N or N-M (1-based) to limit processing.")

    args = p.parse_args()

    pdf_path = Path(args.pdf)
    out_json = Path(args.out_json)
    out_xlsx = Path(args.out_xlsx)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    run(pdf_path, out_json, out_xlsx,args.api_key, args.model_name,args.temperature, args.pages_per_chunk,args.pages)

    print(f"JSON written: {out_json}")
    print(f"XLSX written: {out_xlsx}")

if __name__ == "__main__":
    main()
