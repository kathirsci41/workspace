import base64
import time
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)


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
                "num_predict": 4096,
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
            except Exception as e:
                last_error = e
                logger.warning(
                    f"OCR error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)

        # All retries exhausted
        self._consecutive_failures += 1
        self._last_failure_time = time.time()

        if isinstance(last_error, httpx.TimeoutException):
            raise OCRTimeoutError(f"OCR timed out after {self.max_retries} retries")
        raise OCRServiceError(f"OCR failed after {self.max_retries} retries: {last_error}")
