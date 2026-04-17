"""
Two-Layer OCR extraction client.

Layer 1: GLM-OCR  — image → clean Markdown
Layer 2: Qwen2.5  — Markdown + schema → validated JSON

Uses httpx to communicate with Ollama (same pattern as OCRClient).
Does NOT replace OCRClient — runs alongside it, toggled by feature flag.
"""

import base64
import html
import json
import re
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional

import httpx

from app.services.extraction.glm_ocr_prompts import (
    get_ocr_prompt,
    build_extraction_prompt,
    EXTRACTION_SCHEMAS,
)
from app.services.extraction.field_validator import validate_extracted_fields

logger = logging.getLogger(__name__)

# Retry backoff: 5s, 10s between retries
RETRY_BASE_WAIT = 5
# Max seconds to wait for Ollama readiness
READINESS_TIMEOUT = 60


async def check_models_available(
    base_url: str,
    required_models: list,
    timeout: int = 10,
) -> tuple:
    """Check that required models are available on an Ollama endpoint.

    Returns (True, []) when all models are present.
    Returns (False, [missing_model, ...]) when some are missing or the endpoint
    is unreachable.

    Model name matching is flexible: 'qwen2.5:7b' matches 'qwen2.5:7b' (exact)
    or any available name whose base name equals 'qwen2.5' (tag-stripped fallback).
    """
    url = base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=5), verify=False
        ) as client:
            resp = await client.get(f"{url}/api/tags")
            if resp.status_code != 200:
                logger.warning(
                    f"[ModelCheck] {url}/api/tags returned HTTP {resp.status_code}"
                )
                return False, list(required_models)

            data = resp.json()
            available_names = {m["name"] for m in data.get("models", [])}
            available_bases = {n.split(":")[0] for n in available_names}

            missing = []
            for model in required_models:
                base = model.split(":")[0]
                if model not in available_names and base not in available_bases:
                    missing.append(model)

            return (len(missing) == 0), missing

    except Exception as e:
        logger.warning(f"[ModelCheck] Could not reach {url}: {e}")
        return False, list(required_models)


class TwoLayerClient:
    """Two-layer OCR extraction pipeline using httpx.

    Layer 1 — GLM-OCR converts document image to clean Markdown.
    Layer 2 — Qwen2.5 extracts structured fields from the Markdown.

    Follows the same patterns as OCRClient: circuit breaker, retry
    with backoff, VRAM release, async httpx calls.
    """

    def __init__(
        self,
        base_url: str,
        ocr_model: str = "glm-ocr:latest",
        extractor_model: str = "qwen2.5:7b",
        timeout: int = 120,
        max_retries: int = 3,
        ocr_num_ctx: int = 16384,
        extractor_num_ctx: int = 4096,
        extractor_num_predict: int = 2048,
        save_debug_markdown: bool = False,
        debug_markdown_dir: str = "debug_markdown",
        extractor_base_url: str = "",
        extractor_api_key: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        # Layer 2 can use a different (cloud) endpoint; falls back to base_url
        self.extractor_base_url = (extractor_base_url or base_url).rstrip("/")
        self.extractor_api_key = extractor_api_key
        self.ocr_model = ocr_model
        self.extractor_model = extractor_model
        self.timeout = timeout
        self.max_retries = max_retries
        self.ocr_num_ctx = ocr_num_ctx
        self.extractor_num_ctx = extractor_num_ctx
        self.extractor_num_predict = extractor_num_predict
        self.save_debug_markdown = save_debug_markdown
        self.debug_markdown_dir = debug_markdown_dir

        self._consecutive_failures = 0
        self._last_failure_time = 0.0
        self._cooldown_seconds = 60

        if save_debug_markdown:
            Path(debug_markdown_dir).mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # GPU VRAM management (same as OCRClient)
    # ------------------------------------------------------------------

    async def release_model(self, model: Optional[str] = None) -> None:
        """Ask Ollama to unload a model from GPU VRAM."""
        target = model or self.ocr_model
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15, connect=5), verify=False
            ) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": target, "keep_alive": 0},
                )
                if response.status_code == 200:
                    logger.debug(f"VRAM released for {target}")
                else:
                    logger.warning(
                        f"Model release returned {response.status_code}"
                    )
        except Exception as e:
            logger.warning(f"Model release failed (non-fatal): {e}")

    async def wait_until_ready(self, timeout: int = READINESS_TIMEOUT) -> bool:
        """Poll Ollama /api/tags until it responds."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(5, connect=3), verify=False
                ) as client:
                    resp = await client.get(f"{self.base_url}/api/tags")
                    if resp.status_code == 200:
                        return True
                    if 400 <= resp.status_code < 500:
                        # Wrong URL — retrying won't help
                        logger.error(
                            f"Extraction service returned HTTP {resp.status_code} — check OCR_BASE_URL in .env"
                        )
                        return False
            except Exception:
                pass
            await asyncio.sleep(2)
        logger.error(f"Extraction service not ready after {timeout}s")
        return False

    # ------------------------------------------------------------------
    # Full two-layer extraction
    # ------------------------------------------------------------------

    async def extract(
        self,
        image_data: bytes,
        doc_type: str,
        page_label: str = "",
    ) -> dict:
        """Run the full two-layer pipeline on a single page image.

        Returns:
            dict with keys:
                text       — raw OCR Markdown from Layer 1
                fields     — validated extracted fields from Layer 2
                ocr_ms     — Layer 1 processing time
                extract_ms — Layer 2 processing time
                total_ms   — combined processing time
        """
        start_time = time.time()

        # ── Layer 1: OCR ─────────────────────────────────────────────────
        markdown, ocr_ms = await self._run_ocr_layer(image_data, doc_type)

        if not markdown or len(markdown.strip()) < 20:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                f"[TwoLayer] Layer 1 returned empty/short text for {page_label}"
            )
            return {
                "text": markdown or "",
                "fields": {},
                "ocr_ms": ocr_ms,
                "extract_ms": 0,
                "total_ms": elapsed_ms,
            }

        # Save debug markdown if enabled
        if self.save_debug_markdown and page_label:
            self._save_markdown(markdown, page_label, doc_type)

        # Release OCR model VRAM before loading extractor
        await self.release_model(self.ocr_model)
        await asyncio.sleep(2)  # brief settle time

        # ── Layer 2: Extraction ──────────────────────────────────────────
        fields, extract_ms = await self._run_extraction_layer(
            markdown, doc_type
        )

        # ── Validation ───────────────────────────────────────────────────
        validated = validate_extracted_fields(fields, doc_type)

        total_ms = int((time.time() - start_time) * 1000)

        filled = len([
            v for k, v in validated.items()
            if v is not None and not str(k).startswith("_")
        ])
        logger.info(
            f"[TwoLayer] {doc_type} {page_label} | "
            f"OCR: {ocr_ms}ms | Extract: {extract_ms}ms | "
            f"Fields: {filled}"
        )

        return {
            "text": markdown,
            "fields": validated,
            "ocr_ms": ocr_ms,
            "extract_ms": extract_ms,
            "total_ms": total_ms,
        }

    # ------------------------------------------------------------------
    # Layer 1 — GLM-OCR
    # ------------------------------------------------------------------

    async def _run_ocr_layer(
        self, image_data: bytes, doc_type: str
    ) -> tuple[str, int]:
        """Send image to the configured OCR model and return cleaned text + time.

        Routing:
          - glm-ocr:*     → /api/generate  (custom RENDERER/PARSER, images at top level)
          - qwen2.5vl:* and other vision models → /api/chat with image in message
        """
        ocr_prompt = get_ocr_prompt(doc_type)
        b64_image = base64.b64encode(image_data).decode("utf-8")

        # Pre-emptively unload the extractor model so GLM-OCR has full VRAM
        await self.release_model(self.extractor_model)
        await asyncio.sleep(1)

        if "glm-ocr" in self.ocr_model:
            # GLM-OCR: RENDERER/PARSER only activate via /api/generate
            payload = {
                "model": self.ocr_model,
                "prompt": ocr_prompt,
                "images": [b64_image],
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_ctx": self.ocr_num_ctx,
                },
            }
            raw, elapsed_ms = await self._call_ollama_generate(payload)
        else:
            # Vision-language models (qwen2.5vl etc.): /api/chat with image in message
            payload = {
                "model": self.ocr_model,
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
                    "num_ctx": self.ocr_num_ctx,
                },
            }
            raw, elapsed_ms = await self._call_vision_chat(payload)

        cleaned = self._clean_ocr_output(raw)
        return cleaned, elapsed_ms

    def _clean_ocr_output(self, text: str) -> str:
        """Clean common GLM-OCR output artifacts."""
        # Unescape HTML entities (GLM-OCR outputs HTML tables with &amp; &lt; etc.)
        text = html.unescape(text)
        # Remove repetitive blank HTML table rows (GLM artifact: hallucinated empty rows)
        # Matches <tr> rows where every <td> is empty, repeated 3+ times
        text = re.sub(
            r'(<tr>\s*(?:<td[^>]*>\s*</td>\s*)+</tr>\s*){3,}',
            '',
            text,
            flags=re.IGNORECASE,
        )
        # Remove excessive blank lines
        text = re.sub(r"\n{4,}", "\n\n", text)
        # Fix OCR-dropped slash in dates: 1812/2025 → 18/12/2025
        text = re.sub(r"\b(\d{2})(\d{2})/((?:19|20)\d{2})\b", r"\1/\2/\3", text)
        # Fix I vs 1 confusion directly in the HTML (belt-and-suspenders)
        # Handles: 11TR → 1ITR, IT1R → 1ITR (GLM-OCR reads "1I" prefix as "11" or "IT")
        text = re.sub(r"\b11TR(\d)", r"1ITR\1", text)
        text = re.sub(r"\b11SR(\d)", r"1ISR\1", text)
        text = re.sub(r"\bIT1R(\d)", r"1ITR\1", text)
        text = re.sub(r"\bIT1SR(\d)", r"1ISR\1", text)
        # Fix O vs 0 confusion in SO/Sales Order numbers: 10TM → 1OTM
        text = re.sub(r"\b10TM(\d)", r"1OTM\1", text)
        # Fix D/0 + N/T transposition in DC numbers: 10TN → 1DNT, 10NT → 1DNT
        text = re.sub(r"\b10TN(\w)", r"1DNT\1", text)
        text = re.sub(r"\b10NT(\w)", r"1DNT\1", text)
        # Fix spurious Z in SO numbers: 1OTMZ → 1OTM
        text = re.sub(r"\b1OTMZ(\d)", r"1OTM\1", text)
        # Fix spurious digit 2 in purchase bill numbers: 1PBT2R → 1PBTR
        text = re.sub(r"\b1PBT2R(\d)", r"1PBTR\1", text)
        # Fix T vs F confusion in company PO numbers: 1PFR → 1PTR
        text = re.sub(r"\b1PFR(\d)", r"1PTR\1", text)
        return text.strip()

    # ------------------------------------------------------------------
    # Layer 2 — Extraction LLM
    # ------------------------------------------------------------------

    async def _run_extraction_layer(
        self, markdown: str, doc_type: str, customer_hint: str = ""
    ) -> tuple[dict, int]:
        """Send Markdown to extraction LLM and return parsed fields + time."""

        if doc_type not in EXTRACTION_SCHEMAS:
            logger.warning(f"No schema for doc_type: {doc_type}")
            return {}, 0

        prompt = build_extraction_prompt(doc_type, markdown, customer_hint)

        payload = {
            "model": self.extractor_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",  # Force Ollama JSON mode
            "options": {
                "temperature": 0.0,
                "num_ctx": self.extractor_num_ctx,
                "num_predict": self.extractor_num_predict,
            },
        }

        raw, elapsed_ms = await self._call_extractor(payload)
        fields = self._parse_json_safe(raw)
        fields = self._extract_field_confidences(fields)
        return fields, elapsed_ms

    # ------------------------------------------------------------------
    # Ollama /api/generate caller (for GLM-OCR with custom RENDERER)
    # ------------------------------------------------------------------

    async def _call_ollama_generate(self, payload: dict) -> tuple[str, int]:
        """Call Ollama /api/generate for models with custom RENDERER/PARSER.

        GLM-OCR uses RENDERER glm-ocr and PARSER glm-ocr in its Modelfile.
        These only activate on /api/generate — /api/chat bypasses them.
        Response field is 'response', not 'message.content'.
        """
        # Circuit breaker
        if self._consecutive_failures >= 5:
            elapsed = time.time() - self._last_failure_time
            if elapsed < self._cooldown_seconds:
                raise RuntimeError(
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

                    result = response.json()
                    content = result.get("response", "")
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
                    raise RuntimeError(
                        f"Extraction service unreachable (HTTP {e.response.status_code}) — "
                        f"check the endpoint URL in settings."
                    )
                if e.response.status_code == 500:
                    logger.info(f"Releasing {self.ocr_model} VRAM after 500 error")
                    await self.release_model(self.ocr_model)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"[GLM-OCR] Error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

            if attempt < self.max_retries - 1:
                wait_time = RETRY_BASE_WAIT * (attempt + 1)
                logger.info(f"Waiting {wait_time}s before retry {attempt + 2}")
                await asyncio.sleep(wait_time)
                await self.wait_until_ready()

        self._consecutive_failures += 1
        self._last_failure_time = time.time()
        raise RuntimeError(
            f"Extraction service offline — could not connect to the extraction server."
            if "getaddrinfo" in str(last_error) or "ConnectionError" in type(last_error).__name__
            else f"Extraction failed after {self.max_retries} retries: {last_error}"
        )

    async def _call_extractor(self, payload: dict) -> tuple[str, int]:
        """Call the extraction endpoint (cloud or local) with optional auth.

        Uses extractor_base_url + Authorization header when api_key is set.
        """
        # Circuit breaker
        if self._consecutive_failures >= 5:
            elapsed = time.time() - self._last_failure_time
            if elapsed < self._cooldown_seconds:
                raise RuntimeError(
                    f"[Extractor] Circuit breaker open. "
                    f"Wait {self._cooldown_seconds - elapsed:.0f}s before retrying."
                )
            self._consecutive_failures = 0

        headers = {}
        if self.extractor_api_key:
            headers["Authorization"] = f"Bearer {self.extractor_api_key}"

        last_error = None
        start_time = time.time()

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout, connect=10), verify=False
                ) as client:
                    response = await client.post(
                        f"{self.extractor_base_url}/api/chat",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()

                    result = response.json()
                    content = result.get("message", {}).get("content", "")
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
                    raise RuntimeError(
                        f"Extraction service unreachable (HTTP {e.response.status_code}) — "
                        f"check the endpoint URL in settings."
                    )
            except Exception as e:
                last_error = e
                logger.warning(
                    f"[Extractor] Error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

            if attempt < self.max_retries - 1:
                wait_time = RETRY_BASE_WAIT * (attempt + 1)
                logger.info(f"Waiting {wait_time}s before retry {attempt + 2}")
                await asyncio.sleep(wait_time)

        self._consecutive_failures += 1
        self._last_failure_time = time.time()
        raise RuntimeError(
            f"Extraction service offline — could not connect to the extraction server."
            if "getaddrinfo" in str(last_error) or "ConnectionError" in type(last_error).__name__
            else f"Extractor failed after {self.max_retries} retries: {last_error}"
        )

    # ------------------------------------------------------------------
    # Vision-language model /api/chat caller (for OCR layer with VL models)
    # ------------------------------------------------------------------

    async def _call_vision_chat(self, payload: dict) -> tuple[str, int]:
        """Call Ollama /api/chat for vision-language OCR models (qwen2.5vl etc.).

        Uses self.base_url (OCR endpoint), not extractor_base_url.
        Response field is message.content (standard chat format).
        """
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

                    result = response.json()
                    content = result.get("message", {}).get("content", "")
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
                wait_time = RETRY_BASE_WAIT * (attempt + 1)
                logger.info(f"Waiting {wait_time}s before retry {attempt + 2}")
                await asyncio.sleep(wait_time)

        self._consecutive_failures += 1
        self._last_failure_time = time.time()
        raise RuntimeError(
            f"VisionOCR chat call failed after {self.max_retries} retries: {last_error}"
        )

    # ------------------------------------------------------------------
    # JSON parsing (matches ResponseParser strategies)
    # ------------------------------------------------------------------

    def _parse_json_safe(self, text: str) -> dict:
        """Safely parse JSON from the LLM response.

        Uses the same multi-strategy approach as ResponseParser:
        direct parse → code block → brace extraction → clean+retry.
        """
        text = text.strip()

        # Strategy 1: Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from ```json ... ``` code blocks
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find first { and last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            substring = text[first_brace : last_brace + 1]
            try:
                return json.loads(substring)
            except json.JSONDecodeError:
                # Strategy 4: Clean common issues and retry
                cleaned = self._clean_json(substring)
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass

        logger.warning(
            f"[TwoLayer] Could not parse JSON from extractor: "
            f"{text[:200]}"
        )
        return {}

    @staticmethod
    def _extract_field_confidences(fields: dict) -> dict:
        """Split LLM confidence-wrapped values into flat fields + _field_confidences.

        The extraction prompt asks the LLM to return scalar fields as:
            {"value": <extracted>, "confidence": 0.0-1.0}

        This method unwraps that format:
        - Scalar fields wrapped as {"value": x, "confidence": y} → fields[k] = x
        - _field_confidences dict is populated with {k: y} for each unwrapped field
        - Arrays, None values, and plain scalars are passed through unchanged
        """
        field_confidences: dict[str, float] = {}

        for key in list(fields.keys()):
            val = fields[key]
            if (
                isinstance(val, dict)
                and "value" in val
                and "confidence" in val
                and not isinstance(val.get("value"), list)
            ):
                try:
                    confidence = round(float(val["confidence"]), 3)
                except (TypeError, ValueError):
                    confidence = 0.5
                field_confidences[key] = confidence
                fields[key] = val["value"]

        if field_confidences:
            fields["_field_confidences"] = field_confidences

        return fields

    @staticmethod
    def _clean_json(text: str) -> str:
        """Clean common JSON issues from LLM output."""
        # Remove trailing commas before } or ]
        cleaned = re.sub(r",\s*([}\]])", r"\1", text)
        # Remove control characters
        cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", cleaned)
        # Fix comma-formatted numbers in JSON values
        cleaned = re.sub(
            r'("\s*:\s*)(\d{1,3}(?:,\d{3})+(?:\.\d+)?)',
            lambda m: m.group(1) + m.group(2).replace(",", ""),
            cleaned,
        )
        return cleaned

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------

    def _save_markdown(
        self, markdown: str, page_label: str, doc_type: str
    ) -> None:
        """Save OCR Markdown output to disk for debugging."""
        try:
            safe_label = re.sub(r"[^\w\-.]", "_", page_label)
            out_path = (
                Path(self.debug_markdown_dir)
                / f"{safe_label}_{doc_type}.md"
            )
            out_path.write_text(markdown, encoding="utf-8")
            logger.debug(f"Saved debug markdown: {out_path}")
        except Exception as e:
            logger.debug(f"Could not save debug markdown: {e}")
