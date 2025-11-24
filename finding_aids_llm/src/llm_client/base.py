# src/llm_client/base.py
from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """
    Minimal interface for an LLM client that can process a PDF chunk.
    """

    def generate_chunk(self, pdf_bytes: bytes, prompt: str) -> str:
        """
        Given a mini-PDF (binary bytes) and a textual prompt,
        return the raw text response from the model.

        Implementations may raise exceptions on hard failures.
        """
        ...
