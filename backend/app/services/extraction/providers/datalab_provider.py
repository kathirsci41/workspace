"""Datalab (Marker/Chandra OCR 2) Layer 1 provider.

Uses Datalab's async polling REST API:
  POST /api/v1/convert  →  { request_id }
  GET  /api/v1/convert/{request_id}  →  poll until status == "complete"

Documentation: https://documentation.datalab.to/

Layer 1 only — Datalab is an OCR/document-conversion service, not an
extraction LLM. Pair with OllamaLayer2Provider or OpenAICompatLayer2Provider
for full pipeline coverage.
"""
import asyncio
import logging
import time

import httpx

from app.services.extraction.providers.base import (
    Layer1Provider,
    OcrResult,
    ProviderError,
)

logger = logging.getLogger(__name__)


class DatalabLayer1Provider(Layer1Provider):
    """Converts document page images to markdown via Datalab's conversion API.

    Supports multiple output formats; uses "markdown" for pipeline compatibility.
    health_check() returns (True, "") when api_key is present — Datalab has no
    /api/tags-style readiness endpoint.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.datalab.to",
        timeout: int = 300,
        poll_interval: int = 3,
        max_retries: int = 3,
    ):
        if not api_key:
            raise ValueError("DatalabLayer1Provider requires an api_key")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_retries = max_retries

    @property
    def provider_name(self) -> str:
        return "datalab"

    async def run_ocr(
        self,
        image_data: bytes,
        doc_type: str,
        page_label: str = "",
    ) -> OcrResult:
        """Submit page image to Datalab and poll until markdown is ready."""
        headers = {"X-API-Key": self.api_key}
        start_time = time.time()

        # Step 1: POST multipart upload
        filename = f"{page_label or 'page'}.png"
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as client:
                    resp = await client.post(
                        f"{self.base_url}/api/v1/convert",
                        headers=headers,
                        files={"file": (filename, image_data, "image/png")},
                        data={"output_format": "markdown"},
                    )
                    resp.raise_for_status()
                    request_id = resp.json().get("request_id")
                    if not request_id:
                        raise ProviderError(
                            f"Datalab /api/v1/convert returned no request_id: {resp.text[:200]}"
                        )
                    break
            except httpx.HTTPStatusError as e:
                if 400 <= e.response.status_code < 500:
                    raise ProviderError(
                        f"Datalab rejected upload (HTTP {e.response.status_code}): "
                        f"{e.response.text[:200]}"
                    )
                if attempt == self.max_retries - 1:
                    raise ProviderError(
                        f"Datalab upload failed after {self.max_retries} attempts: {e}"
                    )
                logger.warning(
                    f"[Datalab] Upload attempt {attempt + 1} failed: {e}. Retrying..."
                )
                await asyncio.sleep(5)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise ProviderError(
                        f"Datalab upload failed after {self.max_retries} attempts: {e}"
                    )
                logger.warning(
                    f"[Datalab] Upload attempt {attempt + 1} error: {e}. Retrying..."
                )
                await asyncio.sleep(5)

        # Step 2: Poll until complete (check immediately, then sleep between polls)
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10)) as client:
                    poll = await client.get(
                        f"{self.base_url}/api/v1/convert/{request_id}",
                        headers=headers,
                    )
                    poll.raise_for_status()
                    data = poll.json()
                    status = data.get("status", "")

                    if status == "complete":
                        markdown = data.get("markdown", "") or data.get("content", "")
                        elapsed_ms = int((time.time() - start_time) * 1000)
                        logger.debug(
                            f"[Datalab] {page_label} complete in {elapsed_ms}ms, "
                            f"{len(markdown)} chars"
                        )
                        return OcrResult(
                            markdown=markdown.strip(),
                            elapsed_ms=elapsed_ms,
                            provider=self.provider_name,
                        )

                    if status == "error":
                        raise ProviderError(
                            f"Datalab conversion failed: {data.get('error', data)}"
                        )

                    logger.debug(
                        f"[Datalab] {page_label} status={status}, polling..."
                    )

            except ProviderError:
                raise
            except Exception as e:
                logger.warning(f"[Datalab] Poll error (non-fatal): {e}")

            await asyncio.sleep(self.poll_interval)

        elapsed_s = int(time.time() - start_time)
        raise ProviderError(
            f"Datalab conversion timed out after {elapsed_s}s for request {request_id}"
        )

    async def health_check(self) -> tuple[bool, str]:
        """Returns (True, "") when api_key is set — Datalab has no tags endpoint."""
        if self.api_key:
            return True, ""
        return False, "No Datalab API key configured"
