from __future__ import annotations

import base64
import os
import time
import sys
from typing import Optional, Dict, Any

from openai import OpenAI

from .base import LLMClient


class OpenAIClient(LLMClient):
    """
    OpenAI GPT client wrapper that implements LLMClient.generate_chunk.
    Sends the PDF bytes + OCR prompt via the Responses API.
    """

    def __init__(
        self,
        model_name: str,
        temperature: float = 0.3,
        max_retries: int = 3,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        organization: Optional[str] = None,
        default_filename: str = "document.pdf",
    ) -> None:

        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not found in environment variables.")

        if base_url is None:
            base_url = os.environ.get("OPENAI_BASE_URL")

        if organization is None:
            organization = (
                os.environ.get("OPENAI_ORG_ID")
                or os.environ.get("OPENAI_ORGANIZATION")
            )

        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        if organization:
            kwargs["organization"] = organization

        self.client = OpenAI(**kwargs)
        self.model_name = model_name
        self.temperature = temperature
        self.max_retries = max_retries
        self.default_filename = default_filename

    def generate_chunk(self, pdf_bytes: bytes, prompt: str) -> str:
        """
        Send a mini-PDF as bytes + prompt to the model via the Responses API.
        Retries on failure.
        """
        b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        data_url = f"data:application/pdf;base64,{b64}"

        payload = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": self.default_filename,
                        "file_data": data_url,
                    },
                    {
                        "type": "input_text",
                        "text": prompt,
                    },
                ],
            }
        ]

        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                response = self.client.responses.create(
                    model=self.model_name,
                    input=payload,
                    temperature=self.temperature,
                )
                return self._extract_text(response)
            except Exception as exc:
                print("\n🔥 OpenAI ERROR:", type(exc), exc, "\n", file=sys.stderr)
                last_exc = exc
                if attempt < self.max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                else:
                    break

        raise RuntimeError(
            f"OpenAI request failed after {self.max_retries} attempts"
        ) from last_exc

    @staticmethod
    def _extract_text(response) -> str:
        """
        For the Responses API, response.output_text is the correct getter.
        """
        txt = getattr(response, "output_text", None)
        if txt and str(txt).strip():
            return str(txt)

        # Fallback: JSON dump
        try:
            return response.to_json()  # type: ignore
        except Exception:
            return ""
