from __future__ import annotations

import json
from pathlib import Path

import fitz

import app.services.extraction.glm_ocr_client as glm_ocr_client


def _pdf(path: Path, *, pages: int = 1) -> None:
    document = fitz.open()
    for index in range(pages):
        page = document.new_page(width=336, height=336)
        page.insert_text((24, 48), f"Invoice No TEST-{index + 1:05d}", fontsize=12)
    document.save(path)
    document.close()


def test_ocr_page_diagnostics_include_safe_render_request_metrics(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "ocr-input.pdf"
    _pdf(pdf_path)
    monkeypatch.setattr(glm_ocr_client, "_call_ollama_generate_with_retries", lambda *args, **kwargs: "Invoice No TEST-12345")

    result = glm_ocr_client.extract_text_with_ocr(str(pdf_path), max_pages=1, dpi=150, timeout_seconds=90)

    page = result.pages[0]
    assert page["image_format"] == "png"
    assert page["dpi"] == 150
    assert page["image_bytes"] > 0
    assert page["base64_bytes"] > page["image_bytes"]
    assert page["request_endpoints"] == ["generate", "chat_fallback"]
    assert "Invoice No" not in str(result.diagnostics)


class _JsonResponse:
    status = 200

    def __init__(self, body: dict[str, object]) -> None:
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self._body


def test_ocr_requests_bound_ollama_context_length(monkeypatch):
    requests: list[dict[str, object]] = []

    def fake_urlopen(request, timeout):
        requests.append(json.loads(request.data.decode("utf-8")))
        if request.full_url.endswith("/api/generate"):
            return _JsonResponse({"response": "Invoice No TEST-12345"})
        return _JsonResponse({"message": {"content": "Invoice No TEST-12345"}})

    monkeypatch.setattr(glm_ocr_client, "urlopen", fake_urlopen)

    assert glm_ocr_client._call_generate_endpoint(b"png", timeout_seconds=10)
    assert glm_ocr_client._call_chat_endpoint(b"png", timeout_seconds=10)

    assert requests[0]["options"] == {"num_ctx": 8192}
    assert requests[1]["options"] == {"num_ctx": 8192}


def test_ocr_retries_failed_page_after_later_page_warms_provider(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "ocr-input.pdf"
    _pdf(pdf_path, pages=2)
    responses = iter(
        [
            RuntimeError("generate failed: HTTP 500 model failed to load"),
            "PAGE 2 TEXT",
            "PAGE 1 TEXT",
        ]
    )

    def fake_ocr_call(*args, **kwargs):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(glm_ocr_client, "_call_ollama_generate_with_retries", fake_ocr_call)

    result = glm_ocr_client.extract_text_with_ocr(str(pdf_path), max_pages=2, dpi=150, timeout_seconds=90)

    assert result.text == "PAGE 1 TEXT\nPAGE 2 TEXT"
    assert result.pages[0]["ocr_retry_attempted"] is True
    assert result.pages[0]["initial_error"] == "generate failed: HTTP 500 model failed to load"
    assert "error" not in result.pages[0]
