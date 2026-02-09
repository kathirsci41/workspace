import base64
import logging
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class OCRClient:
    """
    Abstraction layer for GLM-OCR API calls.
    Supports both Ollama (dev) and vLLM (prod) backends.
    """

    def __init__(self):
        settings = get_settings()
        self.backend = settings.ocr_backend       # "ollama" or "vllm"
        self.base_url = settings.ocr_base_url
        self.model_name = settings.ocr_model_name
        # Timeout disabled — extraction runs until completion
        # Time tracking is done per-call instead

    def _encode_image(self, image_path: str) -> str:
        """Read and base64-encode an image file."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    async def extract(self, image_path: str, prompt: str) -> str:
        """
        Send an image + prompt to GLM-OCR and return the raw text response.

        Args:
            image_path: Path to the image file (JPEG/PNG)
            prompt: The extraction prompt with JSON schema

        Returns:
            Raw text response from the model
        """
        image_b64 = self._encode_image(image_path)

        if self.backend == "ollama":
            return await self._call_ollama(image_b64, prompt)
        elif self.backend == "vllm":
            return await self._call_vllm(image_b64, prompt)
        else:
            raise ValueError(f"Unknown OCR backend: {self.backend}")

    async def _call_ollama(self, image_b64: str, prompt: str) -> str:
        """Call Ollama's chat API (no timeout — runs until completion)."""
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [image_b64]
                        }
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.01,
                        "num_predict": 4096,
                        "num_ctx": 8192
                    }
                }
            )
            elapsed = time.perf_counter() - start
            response.raise_for_status()
            data = response.json()
            logger.info(f"Ollama OCR call completed in {elapsed:.2f}s")
            return data["message"]["content"]

    async def _call_vllm(self, image_b64: str, prompt: str) -> str:
        """Call vLLM's OpenAI-compatible API (no timeout — runs until completion)."""
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_b64}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": prompt
                                }
                            ]
                        }
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.01
                }
            )
            elapsed = time.perf_counter() - start
            response.raise_for_status()
            data = response.json()
            logger.info(f"vLLM OCR call completed in {elapsed:.2f}s")
            return data["choices"][0]["message"]["content"]

    async def health_check(self) -> bool:
        """Check if the OCR service is available."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                if self.backend == "ollama":
                    resp = await client.get(f"{self.base_url}/api/tags")
                else:
                    resp = await client.get(f"{self.base_url}/v1/models")
                return resp.status_code == 200
        except Exception:
            return False
