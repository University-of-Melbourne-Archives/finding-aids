# src/config.py
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RunConfig:
    pdf_path: Path
    out_raw: Path
    out_json: Path
    out_csv: Path
    out_xlsx: Path
    out_log: Path
    engine: str          # for now we expect "gemini"
    model_name: str
    temperature: float
    pages_per_chunk: int
    pages: Optional[str]
    max_retries: int = 3


def parse_args() -> RunConfig:
    parser = argparse.ArgumentParser(
        description="finding_aids_llm: PDF → Gemini → structured outputs"
    )

    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to the finding aid PDF.",
    )
    parser.add_argument(
        "--out_raw",
        required=True,
        help="Base directory to save raw model outputs (chunk txt + combined_raw).",
    )
    parser.add_argument(
        "--out_json",
        required=True,
        help="Base directory to save combined JSON outputs.",
    )
    parser.add_argument(
        "--out_csv",
        required=True,
        help="Base directory to save combined CSV outputs.",
    )
    parser.add_argument(
        "--out_xlsx",
        required=True,
        help="Base directory to save combined XLSX outputs.",
    )
    parser.add_argument(
        "--out_log",
        required=True,
        help="Base directory to save logs (parse_issues, run metadata).",
    )
    # src/config.py (or src/utils/config.py in your tree)

    parser.add_argument(
        "--engine",
        default="gemini",
        choices=["gemini", "openai"],  # <-- add "openai"
        help="LLM engine to use. 'gemini' or 'openai'.",
    )


    parser.add_argument(
        "--model_name",
        default="models/gemini-2.5-flash",
        help="Model name or ID for the LLM.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="Sampling temperature for the model.",
    )
    parser.add_argument(
        "--pages_per_chunk",
        type=int,
        default=5,
        help="Number of pages per chunk. If larger than the page range, "
             "a single chunk is used.",
    )
    parser.add_argument(
        "--pages",
        type=str,
        default=None,
        help="Optional page range N or N-M (1-based) to limit processing.",
    )
    parser.add_argument(
        "--max_retries",
        type=int,
        default=3,
        help="Max retries for transient API errors.",
    )

    args = parser.parse_args()

    return RunConfig(
        pdf_path=Path(args.pdf),
        out_raw=Path(args.out_raw),
        out_json=Path(args.out_json),
        out_csv=Path(args.out_csv),
        out_xlsx=Path(args.out_xlsx),
        out_log=Path(args.out_log),
        engine=args.engine,
        model_name=args.model_name,
        temperature=args.temperature,
        pages_per_chunk=int(args.pages_per_chunk),
        pages=args.pages,
        max_retries=args.max_retries,
    )
