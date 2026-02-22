import base64
import time
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

# Retry backoff: 10s, 20s, 30s between retries (gives Ollama time to recover)
RETRY_BASE_WAIT = 10
# Inter-page cooldown after releasing model VRAM
PAGE_COOLDOWN_SECONDS = 10
# Max seconds to wait for Ollama readiness before giving up
READINESS_TIMEOUT = 60


class OCRTimeoutError(Exception):
    pass


class OCRServiceError(Exception):
    pass


class OCRServiceUnavailable(Exception):
    pass


class OCRClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = 120,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._consecutive_failures = 0
        self._last_failure_time = 0.0
        self._cooldown_seconds = 60

    # ------------------------------------------------------------------
    # GPU VRAM management helpers
    # ------------------------------------------------------------------

    async def release_model(self) -> None:
        """Ask Ollama to unload the model from GPU VRAM immediately.

        Uses keep_alive=0 so the model is evicted right after the
        request, freeing GPU memory before the next page is processed.
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15, connect=5)) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "keep_alive": 0},
                )
                if response.status_code == 200:
                    logger.debug("Model VRAM released (keep_alive=0)")
                else:
                    logger.warning(
                        f"Model release returned {response.status_code}"
                    )
        except Exception as e:
            logger.warning(f"Model release request failed (non-fatal): {e}")

    async def wait_until_ready(self, timeout: int = READINESS_TIMEOUT) -> bool:
        """Poll Ollama /api/tags until it responds, up to *timeout* seconds.

        Returns True when Ollama is ready, False on timeout.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(5, connect=3)
                ) as client:
                    resp = await client.get(f"{self.base_url}/api/tags")
                    if resp.status_code == 200:
                        return True
            except Exception:
                pass
            await asyncio.sleep(2)
        logger.error(f"Ollama not ready after {timeout}s")
        return False

    # ------------------------------------------------------------------
    # Core extraction
    # ------------------------------------------------------------------

    async def extract_from_image(self, image_data: bytes, prompt: str) -> dict:
        """Send an image to GLM-OCR via Ollama and get extraction."""
        # Circuit breaker
        if self._consecutive_failures >= 5:
            elapsed = time.time() - self._last_failure_time
            if elapsed < self._cooldown_seconds:
                raise OCRServiceUnavailable(
                    f"OCR service circuit breaker open. "
                    f"Wait {self._cooldown_seconds - elapsed:.0f}s"
                )
            self._consecutive_failures = 0

        # Base64 encode image
        b64_image = base64.b64encode(image_data).decode("utf-8")

        # Build Ollama payload
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [b64_image],
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 2048,
            },
        }

        last_error = None
        start_time = time.time()

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout, connect=10)
                ) as client:
                    response = await client.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                    )
                    response.raise_for_status()

                    result = response.json()
                    content = result.get("message", {}).get("content", "")
                    elapsed_ms = int((time.time() - start_time) * 1000)

                    # Reset failure counter on success
                    self._consecutive_failures = 0

                    return {
                        "text": content,
                        "processing_time_ms": elapsed_ms,
                    }

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    f"OCR timeout (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"OCR HTTP error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                # On 500 errors release model VRAM before retry
                if e.response.status_code == 500:
                    logger.info("Releasing model VRAM after 500 error before retry")
                    await self.release_model()
            except Exception as e:
                last_error = e
                logger.warning(
                    f"OCR error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

            if attempt < self.max_retries - 1:
                # Longer backoff: 10s, 20s, 30s — gives Ollama time to recover
                wait_time = RETRY_BASE_WAIT * (attempt + 1)
                logger.info(f"Waiting {wait_time}s before retry {attempt + 2}")
                await asyncio.sleep(wait_time)
                # Verify Ollama is responsive before retrying
                await self.wait_until_ready()

        # All retries exhausted
        self._consecutive_failures += 1
        self._last_failure_time = time.time()

        if isinstance(last_error, httpx.TimeoutException):
            raise OCRTimeoutError(f"OCR timed out after {self.max_retries} retries")
        raise OCRServiceError(f"OCR failed after {self.max_retries} retries: {last_error}")
