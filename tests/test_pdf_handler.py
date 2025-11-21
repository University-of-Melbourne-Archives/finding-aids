# tests/test_pdf_handler.py
from finding_aids_ocr.core.pdf_handler import PDFHandler


def test_get_chunk_ranges_full_doc(tmp_pdf):
    handler = PDFHandler(tmp_pdf)
    # total_pages=2; pages_per_chunk=1 -> [(1,1), (2,2)]
    ranges = handler.get_chunk_ranges(pages_per_chunk=1, pages=None)
    assert ranges == [(1, 1), (2, 2)]


def test_get_chunk_ranges_specific_range(tmp_pdf):
    handler = PDFHandler(tmp_pdf)
    ranges = handler.get_chunk_ranges(pages_per_chunk=2, pages="1-1")
    assert ranges == [(1, 1)]


def test_create_chunk_returns_bytes(tmp_pdf):
    handler = PDFHandler(tmp_pdf)
    chunk_bytes = handler.create_chunk(start=1, end=2)
    assert isinstance(chunk_bytes, (bytes, bytearray))
    assert len(chunk_bytes) > 0
