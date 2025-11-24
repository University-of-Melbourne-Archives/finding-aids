# src/pdf_chunking/chunking.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from pypdf import PdfReader, PdfWriter
import io


@dataclass
class ChunkSpec:
    """Represents a contiguous page range in the PDF."""
    start_page: int  # 1-based inclusive
    end_page: int    # 1-based inclusive
    index: int       # 1-based chunk index


def parse_pages_arg(pages_arg: str | None, total_pages: int) -> Tuple[int, int]:
    """
    Parse a --pages argument of the form:
      - None → full range 1..total_pages
      - "N" → page N only
      - "A-B" → pages A..B (inclusive, 1-based)
    Clamps to [1, total_pages].
    """
    if not pages_arg:
        return (1, total_pages)

    s = pages_arg.strip()
    if "-" not in s:
        # Single page
        n = int(s)
        n = max(1, min(n, total_pages))
        return (n, n)

    a_str, b_str = s.split("-", 1)
    a, b = int(a_str), int(b_str)
    if b < a:
        a, b = b, a
    a = max(1, min(a, total_pages))
    b = max(1, min(b, total_pages))
    return (a, b)


def make_chunks(start: int, end: int, pages_per_chunk: int) -> List[ChunkSpec]:
    """
    Split [start, end] (1-based inclusive) into non-overlapping chunks
    of at most pages_per_chunk pages.
    """
    if pages_per_chunk <= 0:
        # Single chunk for the whole range
        return [ChunkSpec(start_page=start, end_page=end, index=1)]

    chunks: List[ChunkSpec] = []
    idx = 1
    p = start
    while p <= end:
        q = min(end, p + pages_per_chunk - 1)
        chunks.append(ChunkSpec(start_page=p, end_page=q, index=idx))
        idx += 1
        p = q + 1
    return chunks


def build_mini_pdf_bytes(reader: PdfReader, spec: ChunkSpec) -> bytes:
    """
    Build a mini-PDF containing only pages spec.start_page..spec.end_page (1-based).
    Returns the file as bytes.
    """
    writer = PdfWriter()
    # PdfReader pages are 0-based indices
    for p in range(spec.start_page - 1, spec.end_page):
        writer.add_page(reader.pages[p])
    bio = io.BytesIO()
    writer.write(bio)
    return bio.getvalue()
