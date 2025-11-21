# tests/test_pipeline_smoke.py
import json
from pathlib import Path

import pytest

from finding_aids_ocr.core.pipeline import Pipeline
from finding_aids_ocr.core.json_parser import JSONParser


class FakeLLMClient:
    """Minimal implementation of BaseLLMClient needed for Pipeline tests."""

    def __init__(self):
        self.files = {}
        self.calls = []

    def get_provider_name(self):
        return "fake"

    def validate_credentials(self):
        return True

    def upload_pdf(self, pdf_bytes, filename):
        file_id = f"file_{len(self.files) + 1}"
        self.files[file_id] = pdf_bytes
        return file_id

    def call_with_pdf(self, file_id, prompt):
        # Return a tiny but valid JSON payload matching expected schema.
        payload = {
            "series": [
                {
                    "series": "Series A",
                    "series_notes": "",
                    "items": [
                        {
                            "unit": "Unit 1",
                            "finding_aid_reference": "1.(1)",
                            "title": "Test item",
                            "text": "Test text",
                            "dates": "1900-1905",
                            "item_annotations": "",
                        }
                    ],
                }
            ],
            "unassigned_items": [],
            "document_notes": "Chunk processed.",
        }
        self.calls.append({"file_id": file_id, "prompt": prompt})
        return json.dumps(payload)

    def delete_file(self, file_id):
        self.files.pop(file_id, None)


@pytest.fixture
def fake_llm(monkeypatch):
    from finding_aids_ocr.llm_clients.factory import LLMClientFactory

    fake = FakeLLMClient()

    def _create(provider, model_name=None, temperature=0.3):
        return fake

    monkeypatch.setattr(LLMClientFactory, "create", staticmethod(_create))
    return fake


def test_pipeline_smoke(tmp_pdf, tmp_path, fake_llm, monkeypatch):
    out_json = tmp_path / "out.json"
    out_xlsx = tmp_path / "out.xlsx"

    # We don't care about style here; FakeLLM always returns parenthesis references.
    pipeline = Pipeline(
        pdf_path=tmp_pdf,
        out_json=out_json,
        out_xlsx=out_xlsx,
        llm_provider="openai",         # intercepted by fake_llm fixture
        model_name="dummy-model",
        temperature=0.0,
        pages_per_chunk=1,
        pages=None,
        debug=False,
    )

    # Important: ensure we don't accidentally try real network calls anywhere else.
    pipeline.run()

    # Check files created
    assert out_json.exists()
    assert out_xlsx.exists()

    # Check JSON shape
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert "series" in data
    assert "unassigned_items" in data
    assert "document_notes" in data

    # FakeLLM was called at least once
    assert len(fake_llm.calls) >= 1
