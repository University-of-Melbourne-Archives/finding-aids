# src/llm_client/gemini_client.py
from __future__ import annotations

import os
import time
from typing import Optional

from google import genai
from google.genai import types

from .base import LLMClient



class GeminiClient(LLMClient):
    """
    Gemini client wrapper that implements LLMClient.generate_chunk.

    It uploads the PDF bytes plus a text prompt, and returns the raw text
    response from the model.
    """

    def __init__(
        self,
        model_name: str,
        temperature: float = 0.3,
        max_retries: int = 3,
        api_key: Optional[str] = None,
    ) -> None:
        if api_key is None:
            # Prefer GOOGLE_API_KEY; fallback to GEMINI_API_KEY
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("No Gemini API key set. Please set GOOGLE_API_KEY or GEMINI_API_KEY.")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.temperature = temperature
        self.max_retries = max_retries

    def generate_chunk(self, pdf_bytes: bytes, prompt: str) -> str:
        """
        Send a single PDF (as bytes) + prompt to Gemini and return raw text.
        Retries on transient errors.
        """
        pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")

        try:
            prompt_part = types.Part.from_text(text=prompt)
        except TypeError:
            # Backwards compatibility for older google-genai versions
            prompt_part = types.Part(text=prompt)

        user_content = types.Content(role="user", parts=[pdf_part, prompt_part])

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                # Newer client with GenerateContentConfig
                resp = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[user_content],
                    generation_config=types.GenerateContentConfig(
                        temperature=self.temperature,
                        response_mime_type="application/json",
                    ),
                )
                return self._extract_text(resp)
            except TypeError:
                # Older client signature: no generation_config
                resp = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[user_content],
                )
                return self._extract_text(resp)
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    # simple backoff
                    time.sleep(2 * (attempt + 1))
                else:
                    break

        # If we get here, repeated failures
        raise RuntimeError(f"Gemini request failed after {self.max_retries} attempts") from last_exc

    @staticmethod
    def _extract_text(resp) -> str:
        """
        Try to extract text from a Gemini response in a robust way.
        """
        text = getattr(resp, "text", "") or ""
        if text and text.strip():
            return text

        # Fallback: stitch from first candidate
        try:
            cand = (resp.candidates or [])[0]
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", []) if content is not None else []
            text = "".join(getattr(pt, "text", "") for pt in parts if hasattr(pt, "text"))
        except Exception:
            pass

        return text or ""
