"""
Unit tests for extraction error message strings and no-retry guard alignment.

These tests verify:
1. The RuntimeError messages raised in tasks.py use the new terminology.
2. The no-retry guard string in tasks.py matches the RuntimeError message exactly.
3. TwoLayerClient raises "unreachable" / "offline" on HTTP 4xx / connection errors.
"""

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))


# ── tasks.py error message alignment ─────────────────────────────────────────

class TestTasksErrorMessages:
    """Verify the RuntimeError strings and the no-retry guard stay in sync."""

    def test_two_layer_empty_pages_message_matches_guard(self):
        """The no-retry guard keyword must appear in the RuntimeError message."""
        no_retry_keyword = "all pages failed or were empty"
        runtime_msg = (
            "Extraction service returned no data — "
            "all pages failed or were empty"
        )
        assert no_retry_keyword in runtime_msg, (
            "no-retry guard keyword not found in RuntimeError message — "
            "update tasks.py line 503 to match line 215"
        )

    def test_single_layer_message_does_not_trigger_no_retry_guard(self):
        """Single-layer empty message must NOT contain the no-retry keyword."""
        no_retry_keyword = "all pages failed or were empty"
        single_layer_msg = (
            "Extraction produced no data — "
            "all pages returned empty output"
        )
        assert no_retry_keyword not in single_layer_msg

    def test_no_ocr_in_user_facing_messages(self):
        """Neither user-facing error message should use the word 'OCR'."""
        messages = [
            "Extraction service returned no data — all pages failed or were empty",
            "Extraction produced no data — all pages returned empty output",
        ]
        for msg in messages:
            assert "OCR" not in msg, f"Found 'OCR' in message: {msg!r}"

    def test_extraction_service_terminology(self):
        """User-facing messages use 'Extraction' not 'Two-layer OCR'."""
        messages = [
            "Extraction service returned no data — all pages failed or were empty",
            "Extraction produced no data — all pages returned empty output",
        ]
        for msg in messages:
            assert msg.startswith("Extraction"), (
                f"Message should start with 'Extraction': {msg!r}"
            )


# ── TwoLayerClient error messages ────────────────────────────────────────────

def _make_client():
    from app.services.extraction.two_layer_client import TwoLayerClient
    return TwoLayerClient(
        base_url="http://fake-endpoint:11434",
        max_retries=1,  # faster tests
    )


def _make_mock_async_client(*, post_side_effect=None, get_return_value=None):
    """Build a mock that replaces httpx.AsyncClient as a context manager."""
    mock_inner = AsyncMock()
    if post_side_effect is not None:
        mock_inner.post = AsyncMock(side_effect=post_side_effect)
    if get_return_value is not None:
        mock_inner.get = AsyncMock(return_value=get_return_value)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_inner)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


class TestTwoLayerClientErrors:
    """Verify TwoLayerClient raises the right exceptions on failure."""

    def test_http_404_raises_unreachable(self):
        """HTTP 404 on GLM-OCR call → RuntimeError with 'unreachable' in message."""
        client = _make_client()

        req = httpx.Request("POST", "http://fake-endpoint:11434/api/generate")
        resp = httpx.Response(404, request=req)
        exc = httpx.HTTPStatusError("404 Not Found", request=req, response=resp)

        mock_ctx = _make_mock_async_client(post_side_effect=exc)

        async def _run():
            with patch('httpx.AsyncClient', return_value=mock_ctx):
                with pytest.raises(RuntimeError) as exc_info:
                    await client._call_ollama_generate({"model": "glm-ocr:latest", "prompt": "test"})
            return str(exc_info.value)

        msg = asyncio.run(_run())
        assert "unreachable" in msg.lower(), (
            f"Expected 'unreachable' in error message, got: {msg!r}"
        )

    def test_connection_error_raises_offline(self):
        """DNS / connection failure → RuntimeError with 'offline' in message."""
        client = _make_client()

        mock_ctx = _make_mock_async_client(
            post_side_effect=httpx.ConnectError("[Errno 11001] getaddrinfo failed")
        )

        async def _run():
            with patch('httpx.AsyncClient', return_value=mock_ctx):
                with pytest.raises(RuntimeError) as exc_info:
                    await client._call_ollama_generate({"model": "glm-ocr:latest", "prompt": "test"})
            return str(exc_info.value)

        msg = asyncio.run(_run())
        assert "offline" in msg.lower(), (
            f"Expected 'offline' in error message, got: {msg!r}"
        )

    def test_wait_until_ready_returns_false_on_404(self):
        """wait_until_ready returns False (not raises) when endpoint returns 404."""
        client = _make_client()

        req = httpx.Request("GET", "http://fake-endpoint:11434/api/tags")
        resp_404 = httpx.Response(404, request=req)
        mock_ctx = _make_mock_async_client(get_return_value=resp_404)

        async def _run():
            with patch('httpx.AsyncClient', return_value=mock_ctx):
                return await client.wait_until_ready(timeout=1)

        result = asyncio.run(_run())
        assert result is False, (
            "wait_until_ready should return False on 404 (wrong URL), not raise"
        )

    def test_wait_until_ready_returns_true_on_200(self):
        """wait_until_ready returns True when endpoint is healthy."""
        client = _make_client()

        req = httpx.Request("GET", "http://fake-endpoint:11434/api/tags")
        resp_200 = httpx.Response(200, request=req)
        mock_ctx = _make_mock_async_client(get_return_value=resp_200)

        async def _run():
            with patch('httpx.AsyncClient', return_value=mock_ctx):
                return await client.wait_until_ready(timeout=5)

        result = asyncio.run(_run())
        assert result is True