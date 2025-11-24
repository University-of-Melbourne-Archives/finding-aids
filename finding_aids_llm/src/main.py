# src/main.py
from __future__ import annotations

import sys
import shutil
import json
from pathlib import Path
from typing import List
from datetime import datetime
from dataclasses import asdict

from tqdm import tqdm
from pypdf import PdfReader

from .config import parse_args
from .llm_client.gemini_client import GeminiClient
from .llm_client.openai_client import OpenAIClient
from .prompts.templates import PROMPT_OCR_FLAT_CONFIDENCE
from .pdf_chunking.chunking import (
    parse_pages_arg,
    make_chunks,
    build_mini_pdf_bytes,
    ChunkSpec,
)
from .parsing.json_parsing import parse_chunk_text, ParseIssue
from .postprocess.postprocess import add_page_metadata, ChunkPageInfo
from .output.writers import (
    write_items_json,
    write_items_csv,
    write_items_xlsx,
    write_issues_json,
)


def main() -> None:
    cfg = parse_args()
    started_at = datetime.utcnow()

    # 1. Sanity checks (engine)
    if cfg.engine not in ("gemini", "openai"):
        print(
            f"Engine '{cfg.engine}' is not implemented. "
            f"Use --engine gemini or --engine openai.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Normalise model name for filesystem-safe tag
    model_tag = (
        cfg.model_name
        .replace("/", "_")
        .replace(":", "_")
        .replace(".", "_")
        .replace(" ", "_")
        .lower()
    )

    # Add engine/model_tag to output roots so different engines/models don't collide
    cfg.out_raw = cfg.out_raw / cfg.engine / model_tag
    cfg.out_json = cfg.out_json / cfg.engine / model_tag
    cfg.out_csv = cfg.out_csv / cfg.engine / model_tag
    cfg.out_xlsx = cfg.out_xlsx / cfg.engine / model_tag
    cfg.out_log = cfg.out_log / cfg.engine / model_tag

    # 2. Sanity checks (PDF)
    if not cfg.pdf_path.exists():
        print(f"PDF not found: {cfg.pdf_path}", file=sys.stderr)
        sys.exit(1)

    reader = PdfReader(str(cfg.pdf_path))
    total_pages = len(reader.pages)
    if total_pages == 0:
        print("PDF has 0 pages.", file=sys.stderr)
        sys.exit(1)

    start_page, end_page = parse_pages_arg(cfg.pages, total_pages)
    chunks: List[ChunkSpec] = make_chunks(start_page, end_page, cfg.pages_per_chunk)

    print(f"PDF pages: {total_pages}")
    print(
        f"Processing pages {start_page}-{end_page} in {len(chunks)} chunk(s) "
        f"(pages_per_chunk={cfg.pages_per_chunk})"
    )

    # 3. Prepare per-PDF paths
    # Use stem with underscores instead of spaces to keep filenames shell-friendly
    pdf_stem = cfg.pdf_path.stem.replace(" ", "_")

    # Raw dir: out_raw/<engine>/<model_tag>/<pdf_stem>/ (overwrite if exists)
    raw_dir = cfg.out_raw / pdf_stem
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Logs: out_log/<engine>/<model_tag>/<pdf_stem>/
    log_dir = cfg.out_log / pdf_stem
    log_dir.mkdir(parents=True, exist_ok=True)

    # Flat outputs:
    #   json:  out_json/<engine>/<model_tag>/<pdf_stem>_<model_tag>.json
    #   csv:   out_csv/<engine>/<model_tag>/<pdf_stem>_<model_tag>.csv
    #   xlsx:  out_xlsx/<engine>/<model_tag>/<pdf_stem>_<model_tag>.xlsx
    json_out = cfg.out_json / f"{pdf_stem}_{model_tag}.json"
    csv_out = cfg.out_csv / f"{pdf_stem}_{model_tag}.csv"
    xlsx_out = cfg.out_xlsx / f"{pdf_stem}_{model_tag}.xlsx"

    json_out.parent.mkdir(parents=True, exist_ok=True)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    xlsx_out.parent.mkdir(parents=True, exist_ok=True)

    # 4. LLM client
    if cfg.engine == "gemini":
        client = GeminiClient(
            model_name=cfg.model_name,
            temperature=cfg.temperature,
            max_retries=cfg.max_retries,
        )
    elif cfg.engine == "openai":
        client = OpenAIClient(
            model_name=cfg.model_name,
            temperature=cfg.temperature,
            max_retries=cfg.max_retries,
        )
    else:
        # This should be unreachable due to earlier sanity check
        print(f"Unsupported engine: {cfg.engine}", file=sys.stderr)
        sys.exit(1)

    combined_raw_blocks: List[str] = []
    all_items: List[dict] = []
    all_issues: List[ParseIssue] = []

    # 5. Process each chunk: LLM → raw txt → parse → add page metadata
    with tqdm(total=len(chunks), desc="Chunks", unit="chunk") as bar:
        for spec in chunks:
            mini_pdf = build_mini_pdf_bytes(reader, spec)

            try:
                raw_text = client.generate_chunk(mini_pdf, PROMPT_OCR_FLAT_CONFIDENCE)
            except Exception as exc:  # noqa: BLE001
                raw_text = f"ERROR for pages {spec.start_page}-{spec.end_page}: {exc}"
                print(raw_text, file=sys.stderr)

            # Save per-chunk raw txt: chunk<start>-<end>.txt
            chunk_file = raw_dir / f"chunk{spec.start_page}-{spec.end_page}.txt"
            chunk_file.write_text(raw_text, encoding="utf-8")

            # For combined_raw.txt
            header = (
                f"\n\n===== CHUNK {spec.index} "
                f"(pages {spec.start_page}-{spec.end_page}) =====\n\n"
            )
            combined_raw_blocks.append(header + raw_text)

            # Parse and enrich this chunk's items
            valid_items, all_issues = parse_chunk_text(
                raw_text,
                chunk_id=f"chunk{spec.start_page}-{spec.end_page}",
                issues=all_issues,
            )

            if valid_items:
                page_info = ChunkPageInfo(
                    chunk_index=spec.index,
                    start_page=spec.start_page,
                    end_page=spec.end_page,
                )
                enriched = add_page_metadata(valid_items, page_info)
                all_items.extend(enriched)

            bar.update(1)

    # Save combined raw output
    (raw_dir / "combined_raw.txt").write_text(
        "".join(combined_raw_blocks), encoding="utf-8"
    )

    # 6. Write structured outputs (JSON / CSV / XLSX)
    write_items_json(json_out, all_items)
    write_items_csv(csv_out, all_items)
    write_items_xlsx(xlsx_out, all_items)

    # 7. Logs: parse issues + run metadata
    issues_out = log_dir / "parse_issues.json"
    write_issues_json(issues_out, [i.to_dict() for i in all_issues])

    finished_at = datetime.utcnow()

    # Make RunConfig JSON-safe (convert Paths to str)
    cfg_dict = asdict(cfg)
    for k, v in cfg_dict.items():
        if isinstance(v, Path):
            cfg_dict[k] = str(v)

    run_metadata = {
        "pdf_stem": pdf_stem,
        "engine": cfg.engine,
        "model_name": cfg.model_name,
        "model_tag": model_tag,
        "config": cfg_dict,
        "started_at_utc": started_at.isoformat() + "Z",
        "finished_at_utc": finished_at.isoformat() + "Z",
        "total_pages": total_pages,
        "processed_start_page": start_page,
        "processed_end_page": end_page,
        "num_chunks": len(chunks),
        "num_items": len(all_items),
        "num_issues": len(all_issues),
        "paths": {
            "raw_dir": str(raw_dir),
            "json_out": str(json_out),
            "csv_out": str(csv_out),
            "xlsx_out": str(xlsx_out),
            "log_dir": str(log_dir),
            "issues_out": str(issues_out),
        },
    }

    (log_dir / "run_metadata.json").write_text(
        json.dumps(run_metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n✨ Completed end-to-end pipeline.")
    print(f"- Raw chunks & combined_raw: {raw_dir}")
    print(f"- JSON:   {json_out}")
    print(f"- CSV:    {csv_out}")
    print(f"- XLSX:   {xlsx_out}")
    print(f"- Issues: {issues_out}")
    print(f"- Metadata: {log_dir / 'run_metadata.json'}")


if __name__ == "__main__":
    main()
