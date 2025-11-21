# src/postprocess/postprocess.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ChunkPageInfo:
    """
    Metadata about a single chunk's page range.

    chunk_index:
        1-based index of the chunk (as used in main.py / progress bar).
    start_page:
        Inclusive start page of this chunk (1-based).
    end_page:
        Inclusive end page of this chunk (1-based).
    """
    chunk_index: int
    start_page: int
    end_page: int


def add_page_metadata(
    items: List[Dict[str, Any]],
    page_info: ChunkPageInfo,
) -> List[Dict[str, Any]]:
    """
    Attach page/chunk metadata to each item from a given chunk.

    New structure for each item:

        {
          "page": {
            "chunk": "1",
            "page_number": "1-5"
          },
          ... original fields ...
        }

    This does not modify the input list; it returns a new list.
    """
    out: List[Dict[str, Any]] = []
    page_number_str = f"{page_info.start_page}-{page_info.end_page}"

    for item in items:
        new_item = {
            "page": {
                "chunk": str(page_info.chunk_index),
                "page_number": page_number_str,
            },
            **item,
        }
        out.append(new_item)

    return out
