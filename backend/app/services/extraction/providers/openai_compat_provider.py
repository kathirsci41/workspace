"""OpenAI-compatible Layer 1 (vision OCR) and Layer 2 (extraction) providers.

Covers any endpoint that speaks the OpenAI Chat Completions API:
  - vLLM (local or remote)
  - LM Studio
  - Groq
  - OpenAI
  - Anthropic (via openai-compat shim)
  - Any other OpenAI-API-compatible service

Layer 1 sends the image as a base64 data-URL in the messages array.
Layer 2 sends the markdown text with response_format: {type: "json_object"}.
"""
import asyncio
import base64
import logging
import time

import httpx

from app.services.extraction.glm_ocr_prompts import (
    get_ocr_prompt,
    build_extraction_prompt,
    EXTRACTION_SCHEMAS,
)
from app.services.extraction.providers.base import (
    Layer1Provider,
    Layer2Provider,
    OcrResult,
    ExtractionResult,
    ProviderError,
)
from app.services.extraction.providers.json_utils import parse_json_safe

logger = logging.getLogger(__name__)

_RETRY_BASE_WAIT = 5


class OpenAICompatLayer1Provider(Layer1Provider):
    """Vision OCR via any OpenAI-compatible /v1/chat/completions endpoint.

    Sends the page image as a base64 data-URL content item alongside the OCR
    prompt. Works with any vision-capable model (GPT-4o, LLaVA, InternVL, etc.).

    NOTE: Does NOT apply _clean_ocr_output() — that cleaner is GLM-OCR-specific.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: int = 120,
        max_retries: int = 3,
        max_tokens: int = 4096,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_tokens = max_tokens

    @property
    def provider_name(self) -> str:
        return f"openai_compat/{self.model}"

    async def run_ocr(
        self,
        image_data: bytes,
        doc_type: str,
        page_label: str = "",
    ) -> OcrResult:
        """Convert a page image to markdown text via vision chat completions."""
        ocr_prompt = get_ocr_prompt(doc_type)
        b64 = base64.b64encode(image_data).decode("utf-8")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "high",
                            },
                        },
                        {"type": "text", "text": ocr_prompt},
                    ],
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": 0.0,
        }

        raw, elapsed_ms = await _call_chat_completions(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=self.max_retries,
            payload=payload,
            label="OCR",
        )
        return OcrResult(
            markdown=raw.strip(),
            elapsed_ms=elapsed_ms,
            provider=self.provider_name,
        )

    async def health_check(self) -> tuple[bool, str]:
        """GET /v1/models and verify the model is listed.

        Skips the check when api_key is set (cloud endpoints rarely need
        an on-prem readiness check and often rate-limit /v1/models).
        """
        if self.api_key or _is_cloud_url(self.base_url):
            return True, ""
        return await _openai_compat_health_check(self.base_url, self.model)


class OpenAICompatLayer2Provider(Layer2Provider):
    """Text extraction via any OpenAI-compatible /v1/chat/completions endpoint.

    Uses response_format: {"type": "json_object"} to enforce JSON output.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: int = 120,
        max_retries: int = 3,
        max_tokens: int = 4096,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_tokens = max_tokens

    @property
    def provider_name(self) -> str:
        return f"openai_compat/{self.model}"

    async def run_extraction(
        self,
        markdown: str,
        doc_type: str,
        customer_hint: str = "",
    ) -> ExtractionResult:
        """Extract structured fields from markdown text."""
        if doc_type not in EXTRACTION_SCHEMAS:
            logger.warning(f"No schema for doc_type: {doc_type}")
            return ExtractionResult(fields={}, elapsed_ms=0, provider=self.provider_name)

        prompt = build_extraction_prompt(doc_type, markdown, customer_hint)

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "max_tokens": self.max_tokens,
            "temperature": 0.0,
        }

        raw, elapsed_ms = await _call_chat_completions(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=self.max_retries,
            payload=payload,
            label=f"Extraction/{doc_type}",
        )
        fields = parse_json_safe(raw, context=f"OpenAICompatL2/{doc_type}")
        return ExtractionResult(
            fields=fields,
            elapsed_ms=elapsed_ms,
            provider=self.provider_name,
        )

    async def health_check(self) -> tuple[bool, str]:
        if self.api_key or _is_cloud_url(self.base_url):
            return True, ""
        return await _openai_compat_health_check(self.base_url, self.model)


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------

async def _call_chat_completions(
    base_url: str,
    api_key: str,
    timeout: int,
    max_retries: int,
    payload: dict,
    label: str = "",
) -> tuple[str, int]:
    """POST to /v1/chat/completions with retry + error handling.

    Used by both OpenAICompatLayer1Provider and OpenAICompatLayer2Provider.
    Returns (content_string, elapsed_ms).
    Raises ProviderError on unrecoverable failure.
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    last_error = None
    start_time = time.time()

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=10), verify=False
            ) as client:
                response = await client.post(
                    f"{base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                content = (
                    response.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                elapsed_ms = int((time.time() - start_time) * 1000)
                return content, elapsed_ms

        except httpx.TimeoutException as e:
            last_error = e
            logger.warning(
                f"[OpenAICompat/{label}] Timeout "
                f"(attempt {attempt + 1}/{max_retries}): {e}"
            )
        except httpx.HTTPStatusError as e:
            last_error = e
            logger.warning(
                f"[OpenAICompat/{label}] HTTP {e.response.status_code} "
                f"(attempt {attempt + 1}/{max_retries}): {e}"
            )
            if 400 <= e.response.status_code < 500:
                raise ProviderError(
                    f"OpenAI-compat endpoint rejected request "
                    f"(HTTP {e.response.status_code}): {e.response.text[:200]}"
                )
        except Exception as e:
            last_error = e
            logger.warning(
                f"[OpenAICompat/{label}] Error "
                f"(attempt {attempt + 1}/{max_retries}): {e}"
            )

        if attempt < max_retries - 1:
            wait_time = _RETRY_BASE_WAIT * (attempt + 1)
            logger.info(f"Waiting {wait_time}s before retry {attempt + 2}")
            await asyncio.sleep(wait_time)

    raise ProviderError(
        f"OpenAI-compat {label} failed after {max_retries} retries: {last_error}"
    )


def _is_cloud_url(url: str) -> bool:
    """Return True for known cloud hostnames that do not expose /v1/models."""
    cloud_hosts = ("api.openai.com", "api.groq.com", "api.anthropic.com",
                   "generativelanguage.googleapis.com")
    return any(h in url for h in cloud_hosts)


async def _openai_compat_health_check(base_url: str, model: str) -> tuple[bool, str]:
    """GET /v1/models and verify the model is listed."""
    url = base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=5), verify=False
        ) as client:
            resp = await client.get(f"{url}/v1/models")
            if resp.status_code != 200:
                return False, f"/v1/models returned HTTP {resp.status_code}"

            data = resp.json()
            model_ids = {m["id"] for m in data.get("data", [])}
            if model not in model_ids:
                return False, f"Model '{model}' not found at {url}"

            return True, ""

    except Exception as e:
        return False, f"Could not reach {url}: {e}"
