# tests/conftest.py
import json
import textwrap
from pathlib import Path

import pytest

from finding_aids_ocr.core.json_parser import JSONParser
from finding_aids_ocr.handlers.parenthesis_handler import ParenthesisHandler
from finding_aids_ocr.post_processing.date_range import enrich_rows_with_date_ranges


@pytest.fixture
def json_parser():
    return JSONParser()


@pytest.fixture
def parenthesis_handler():
    return ParenthesisHandler()


@pytest.fixture
def sample_chunk_result():
    """Minimal but realistic chunk_result structure."""
    return {
        "series": [
            {
                "series": "Series A",
                "series_notes": "Some notes",
                "items": [
                    {
                        "unit": "Unit 1",
                        "finding_aid_reference": "25.(3)",
                        "title": "Deed of partnership",
                        "text": "Legal docs 1837-1952",
                        "dates": "1837-1952",
                        "item_annotations": "",
                    },
                    {
                        "unit": "Unit 1",
                        "finding_aid_reference": "25.(4)",
                        "title": "Correspondence",
                        "text": "Letters and notes",
                        "dates": "1850-1860",
                        "item_annotations": "",
                    },
                ],
            }
        ],
        "unassigned_items": [
            {
                "unit": "",
                "finding_aid_reference": "",
                "title": "Loose material",
                "text": "Unsorted legal docs",
                "dates": "n.d.",
                "item_annotations": "check later",
            }
        ],
        "document_notes": "Introductory notes for the finding aid.",
    }


@pytest.fixture
def sample_flat_rows(sample_chunk_result, parenthesis_handler):
    """Flattened rows from a single chunk, roughly matching your Flattener output."""
    from finding_aids_ocr.post_processing.flattener import Flattener

    rows = Flattener(parenthesis_handler).flatten(sample_chunk_result)
    return rows


@pytest.fixture
def tmp_pdf(tmp_path):
    """Create a tiny 2-page PDF on disk for PDFHandler tests."""
    from pypdf import PdfWriter

    pdf_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    with pdf_path.open("wb") as f:
        writer.write(f)
    return pdf_path
