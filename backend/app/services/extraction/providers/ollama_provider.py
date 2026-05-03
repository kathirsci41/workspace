"""Ollama Layer 1 (OCR) and Layer 2 (extraction) providers.

Logic migrated from two_layer_client.py — adapted to Layer1Provider /
Layer2Provider interfaces. two_layer_client.py is kept as-is during the
transition and is not modified here.
"""
import asyncio
import base64
import html
import logging
import re
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

# Retry backoff: 5s, 10s between retries
_RETRY_BASE_WAIT = 5
# Max seconds to poll for Ollama readiness
_READINESS_TIMEOUT = 60


class OllamaLayer1Provider(Layer1Provider):
    """Ollama Layer 1: image bytes → markdown text via /api/generate or /api/chat.

    Routing:
      - glm-ocr:*        → /api/generate  (RENDERER/PARSER only work on generate)
      - other VL models  → /api/chat with image in message
    """

    def __init__(
        self,
        base_url: str,
        model: str = "glm-ocr:latest",
        timeout: int = 120,
        max_retries: int = 3,
        num_ctx: int = 16384,
        save_debug_markdown: bool = False,
        debug_markdown_dir: str = "debug_markdown",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.num_ctx = num_ctx
        self.save_debug_markdown = save_debug_markdown
        self.debug_markdown_dir = debug_markdown_dir

        self._consecutive_failures = 0
        self._last_failure_time = 0.0
        self._cooldown_seconds = 60

        if save_debug_markdown:
            from pathlib import Path
            Path(debug_markdown_dir).mkdir(exist_ok=True)

    @property
    def provider_name(self) -> str:
        return f"ollama/{self.model}"

    async def run_ocr(
        self,
        image_data: bytes,
        doc_type: str,
        page_label: str = "",
    ) -> OcrResult:
        """Convert a single page image to markdown text."""
        ocr_prompt = get_ocr_prompt(doc_type)
        b64_image = base64.b64encode(image_data).decode("utf-8")

        if "glm-ocr" in self.model:
            payload = {
                "model": self.model,
                "prompt": ocr_prompt,
                "images": [b64_image],
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_ctx": self.num_ctx,
                },
            }
            raw, elapsed_ms = await self._call_generate(payload)
        else:
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": ocr_prompt,
                        "images": [b64_image],
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_ctx": self.num_ctx,
                },
            }
            raw, elapsed_ms = await self._call_vision_chat(payload)

        cleaned = self._clean_ocr_output(raw)

        if self.save_debug_markdown and page_label and cleaned:
            self._save_markdown(cleaned, page_label, doc_type)

        return OcrResult(markdown=cleaned, elapsed_ms=elapsed_ms, provider=self.provider_name)

    async def release_vram(self) -> None:
        """Ask Ollama to unload the OCR model from GPU VRAM."""
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15, connect=5), verify=False
            ) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "keep_alive": 0},
                )
                if response.status_code == 200:
                    logger.debug(f"VRAM released for {self.model}")
                else:
                    logger.warning(f"Model release returned {response.status_code}")
        except Exception as e:
            logger.warning(f"Model release failed (non-fatal): {e}")

    async def wait_until_ready(self, timeout: int = _READINESS_TIMEOUT) -> None:
        """Poll Ollama /api/tags until it responds."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(5, connect=3), verify=False
                ) as client:
                    resp = await client.get(f"{self.base_url}/api/tags")
                    if resp.status_code == 200:
                        return
                    if 400 <= resp.status_code < 500:
                        logger.error(
                            f"Extraction service returned HTTP {resp.status_code} "
                            f"— check OCR_BASE_URL in .env"
                        )
                        return
            except Exception:
                pass
            await asyncio.sleep(2)
        logger.error(f"Extraction service not ready after {timeout}s")

    async def health_check(self) -> tuple[bool, str]:
        """GET /api/tags and verify the OCR model is available."""
        return await _ollama_health_check(self.base_url, self.model)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clean_ocr_output(self, text: str) -> str:
        """Clean GLM-OCR-specific output artifacts."""
        text = html.unescape(text)
        text = re.sub(
            r'(<tr>\s*(?:<td[^>]*>\s*</td>\s*)+</tr>\s*){3,}',
            '',
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\n{4,}", "\n\n", text)
        text = re.sub(r"\b(\d{2})(\d{2})/((?:19|20)\d{2})\b", r"\1/\2/\3", text)
        text = re.sub(r"\b11TR(\d)", r"1ITR\1", text)
        text = re.sub(r"\b11SR(\d)", r"1ISR\1", text)
        text = re.sub(r"\bIT1R(\d)", r"1ITR\1", text)
        text = re.sub(r"\bIT1SR(\d)", r"1ISR\1", text)
        text = re.sub(r"\b10TM(\d)", r"1OTM\1", text)
        text = re.sub(r"\b10TN(\w)", r"1DNT\1", text)
        text = re.sub(r"\b10NT(\w)", r"1DNT\1", text)
        text = re.sub(r"\b1OTMZ(\d)", r"1OTM\1", text)
        text = re.sub(r"\b1PBT2R(\d)", r"1PBTR\1", text)
        text = re.sub(r"\b1PFR(\d)", r"1PTR\1", text)
        return text.strip()

    def _save_markdown(self, text: str, page_label: str, doc_type: str) -> None:
        from pathlib import Path
        safe_label = re.sub(r"[^\w\-]", "_", page_label)
        path = Path(self.debug_markdown_dir) / f"{safe_label}_{doc_type}.md"
        try:
            path.write_text(text, encoding="utf-8")
            logger.debug(f"Debug markdown saved: {path}")
        except Exception as e:
            logger.warning(f"Could not save debug markdown: {e}")

    async def _call_generate(self, payload: dict) -> tuple[str, int]:
        """Call Ollama /api/generate (GLM-OCR with RENDERER/PARSER)."""
        if self._consecutive_failures >= 5:
            elapsed = time.time() - self._last_failure_time
            if elapsed < self._cooldown_seconds:
                raise ProviderError(
                    f"[GLM-OCR] Circuit breaker open. "
                    f"Wait {self._cooldown_seconds - elapsed:.0f}s before retrying."
                )
            self._consecutive_failures = 0

        last_error = None
        start_time = time.time()

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout, connect=10), verify=False
                ) as client:
                    response = await client.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                    )
                    response.raise_for_status()
                    content = response.json().get("response", "")
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    self._consecutive_failures = 0
                    return content, elapsed_ms

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    f"[GLM-OCR] Timeout (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"[GLM-OCR] HTTP {e.response.status_code} "
                    f"(attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if 400 <= e.response.status_code < 500:
                    self._consecutive_failures += 1
                    self._last_failure_time = time.time()
                    raise ProviderError(
                        f"Extraction service unreachable (HTTP {e.response.status_code}) — "
                        f"check the endpoint URL in settings."
                    )
                if e.response.status_code == 500:
                    await self.release_vram()
            except Exception as e:
                last_error = e
                logger.warning(
                    f"[GLM-OCR] Error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

            if attempt < self.max_retries - 1:
                wait_time = _RETRY_BASE_WAIT * (attempt + 1)
                logger.info(f"Waiting {wait_time}s before retry {attempt + 2}")
                await asyncio.sleep(wait_time)
                await self.wait_until_ready()

        self._consecutive_failures += 1
        self._last_failure_time = time.time()
        raise ProviderError(
            "Extraction service offline — could not connect to the extraction server."
            if "getaddrinfo" in str(last_error) or "ConnectionError" in type(last_error).__name__
            else f"Extraction failed after {self.max_retries} retries: {last_error}"
        )

    async def _call_vision_chat(self, payload: dict) -> tuple[str, int]:
        """Call Ollama /api/chat for vision-language OCR models (qwen2.5vl etc.)."""
        if self._consecutive_failures >= 5:
            elapsed = time.time() - self._last_failure_time
            if elapsed < self._cooldown_seconds:
                raise ProviderError(
                    f"[VisionOCR] Circuit breaker open. "
                    f"Wait {self._cooldown_seconds - elapsed:.0f}s before retrying."
                )
            self._consecutive_failures = 0

        last_error = None
        start_time = time.time()

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout, connect=10), verify=False
                ) as client:
                    response = await client.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                    )
                    response.raise_for_status()
                    content = response.json().get("message", {}).get("content", "")
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    self._consecutive_failures = 0
                    return content, elapsed_ms

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    f"[VisionOCR] Timeout (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"[VisionOCR] HTTP {e.response.status_code} "
                    f"(attempt {attempt + 1}/{self.max_retries}): {e}"
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    f"[VisionOCR] Error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

            if attempt < self.max_retries - 1:
                wait_time = _RETRY_BASE_WAIT * (attempt + 1)
                logger.info(f"Waiting {wait_time}s before retry {attempt + 2}")
                await asyncio.sleep(wait_time)

        self._consecutive_failures += 1
        self._last_failure_time = time.time()
        raise ProviderError(
            f"VisionOCR chat call failed after {self.max_retries} retries: {last_error}"
        )


class OllamaLayer2Provider(Layer2Provider):
    """Ollama Layer 2: markdown text → structured JSON via /api/chat.

    Supports optional Bearer auth for cloud-hosted Ollama-compatible endpoints.
    """

    def __init__(
        self,
        base_url: str,
        model: str = "qwen2.5:7b",
        timeout: int = 120,
        max_retries: int = 3,
        num_ctx: int = 4096,
        num_predict: int = 4096,
        api_key: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.api_key = api_key

        self._consecutive_failures = 0
        self._last_failure_time = 0.0
        self._cooldown_seconds = 60

    @property
    def provider_name(self) -> str:
        return f"ollama/{self.model}"

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
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }

        raw, elapsed_ms = await self._call_extractor(payload)
        fields = parse_json_safe(raw, context=f"OllamaL2/{doc_type}")
        return ExtractionResult(fields=fields, elapsed_ms=elapsed_ms, provider=self.provider_name)

    async def health_check(self) -> tuple[bool, str]:
        """Verify the extraction model is available.

        Skips /api/tags check when api_key is set (cloud endpoint with no tags API).
        """
        if self.api_key:
            return True, ""
        return await _ollama_health_check(self.base_url, self.model)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call_extractor(self, payload: dict) -> tuple[str, int]:
        """Call /api/chat with optional Bearer auth."""
        if self._consecutive_failures >= 5:
            elapsed = time.time() - self._last_failure_time
            if elapsed < self._cooldown_seconds:
                raise ProviderError(
                    f"[Extractor] Circuit breaker open. "
                    f"Wait {self._cooldown_seconds - elapsed:.0f}s before retrying."
                )
            self._consecutive_failures = 0

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error = None
        start_time = time.time()

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout, connect=10), verify=False
                ) as client:
                    response = await client.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                    content = response.json().get("message", {}).get("content", "")
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    self._consecutive_failures = 0
                    return content, elapsed_ms

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    f"[Extractor] Timeout (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"[Extractor] HTTP {e.response.status_code} "
                    f"(attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if 400 <= e.response.status_code < 500:
                    self._consecutive_failures += 1
                    self._last_failure_time = time.time()
                    raise ProviderError(
                        f"Extraction service unreachable (HTTP {e.response.status_code}) — "
                        f"check the endpoint URL in settings."
                    )
            except Exception as e:
                last_error = e
                logger.warning(
                    f"[Extractor] Error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

            if attempt < self.max_retries - 1:
                wait_time = _RETRY_BASE_WAIT * (attempt + 1)
                logger.info(f"Waiting {wait_time}s before retry {attempt + 2}")
                await asyncio.sleep(wait_time)

        self._consecutive_failures += 1
        self._last_failure_time = time.time()
        raise ProviderError(
            "Extraction service offline — could not connect to the extraction server."
            if "getaddrinfo" in str(last_error) or "ConnectionError" in type(last_error).__name__
            else f"Extractor failed after {self.max_retries} retries: {last_error}"
        )


class OCRClientLayer1Adapter(Layer1Provider):
    """Adapter wrapping the legacy OCRClient behind the Layer1Provider interface.

    Used by build_pipeline_from_config() when neither layer1_provider nor
    ocr_two_layer_enabled is set — preserves the original single-layer path.
    """

    def __init__(self, settings):
        from app.services.extraction.ocr_client import OCRClient
        from app.services.extraction.prompts import EXTRACTION_PROMPTS
        self._client = OCRClient(
            base_url=settings.ocr_base_url,
            model=settings.ocr_model_name,
            timeout=settings.ocr_timeout,
            max_retries=settings.ocr_max_retries,
        )
        self._prompts = EXTRACTION_PROMPTS

    @property
    def provider_name(self) -> str:
        return "ocr_client_legacy"

    async def run_ocr(
        self,
        image_data: bytes,
        doc_type: str,
        page_label: str = "",
    ) -> OcrResult:
        config = self._prompts.get(doc_type, {})
        prompt = config.get("prompt", "")
        start = time.time()
        result = await self._client.extract_from_image(image_data, prompt)
        elapsed_ms = int((time.time() - start) * 1000)
        # OCRClient returns a dict; pull text if present
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        return OcrResult(markdown=text, elapsed_ms=elapsed_ms, provider=self.provider_name)

    async def health_check(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10, connect=5), verify=False
            ) as client:
                resp = await client.get(f"{self._client.base_url}/api/tags")
                if resp.status_code == 200:
                    return True, ""
                return False, f"HTTP {resp.status_code}"
        except Exception as e:
            return False, str(e)


# ------------------------------------------------------------------
# Shared health-check helper (avoids duplication between L1/L2)
# ------------------------------------------------------------------

async def _ollama_health_check(base_url: str, model: str) -> tuple[bool, str]:
    """GET /api/tags and verify model is in the list."""
    url = base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=5), verify=False
        ) as client:
            resp = await client.get(f"{url}/api/tags")
            if resp.status_code != 200:
                return False, f"/api/tags returned HTTP {resp.status_code}"

            data = resp.json()
            available_names = {m["name"] for m in data.get("models", [])}
            available_bases = {n.split(":")[0] for n in available_names}
            base = model.split(":")[0]

            if model not in available_names and base not in available_bases:
                return False, f"Model '{model}' not found on {url}"

            return True, ""

    except Exception as e:
        return False, f"Could not reach {url}: {e}"
