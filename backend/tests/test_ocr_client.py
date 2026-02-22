"""Tests for OCRClient (circuit breaker, retries, extraction)."""
import time
import pytest
import asyncio
import httpx

from unittest.mock import AsyncMock, patch, MagicMock

from app.services.extraction.ocr_client import (
    OCRClient,
    OCRTimeoutError,
    OCRServiceError,
    OCRServiceUnavailable,
    RETRY_BASE_WAIT,
    PAGE_COOLDOWN_SECONDS,
    READINESS_TIMEOUT,
)


def run_async(coro):
    return asyncio.run(coro)


@pytest.fixture
def client():
    return OCRClient(
        base_url="http://localhost:11434",
        model="glm-ocr",
        timeout=10,
        max_retries=3,
    )


# ── Exception classes ────────────────────────────────────────────────────

class TestExceptions:
    def test_timeout_error_is_exception(self):
        assert issubclass(OCRTimeoutError, Exception)

    def test_service_error_is_exception(self):
        assert issubclass(OCRServiceError, Exception)

    def test_unavailable_is_exception(self):
        assert issubclass(OCRServiceUnavailable, Exception)

    def test_timeout_error_message(self):
        e = OCRTimeoutError("timed out")
        assert str(e) == "timed out"


# ── Constructor ──────────────────────────────────────────────────────────

class TestInit:
    def test_strips_trailing_slash(self):
        c = OCRClient(base_url="http://host:1234/", model="m")
        assert c.base_url == "http://host:1234"

    def test_default_values(self):
        c = OCRClient(base_url="http://host", model="m")
        assert c.timeout == 120
        assert c.max_retries == 3
        assert c._consecutive_failures == 0
        assert c._cooldown_seconds == 60


# ── Module-level constants ───────────────────────────────────────────────

class TestConstants:
    def test_retry_base_wait(self):
        assert RETRY_BASE_WAIT == 10

    def test_page_cooldown_seconds(self):
        assert PAGE_COOLDOWN_SECONDS == 10

    def test_readiness_timeout(self):
        assert READINESS_TIMEOUT == 60


# ── release_model ────────────────────────────────────────────────────────

class TestReleaseModel:
    def test_posts_keep_alive_zero(self, client):
        """release_model sends keep_alive=0 to unload from GPU."""
        captured: dict[str, object] = {}

        async def capture_post(url, json=None, **kwargs):
            captured["url"] = url
            captured["json"] = json
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            return mock_resp

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=capture_post)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            run_async(client.release_model())

        assert captured["url"] == "http://localhost:11434/api/generate"
        assert captured["json"]["model"] == "glm-ocr"
        assert captured["json"]["keep_alive"] == 0

    def test_non_200_logs_warning_but_does_not_raise(self, client):
        """Non-200 response is a warning, not an exception."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_instance.post = AsyncMock(return_value=mock_resp)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            # Should not raise
            run_async(client.release_model())

    def test_network_error_does_not_raise(self, client):
        """Network errors during release are swallowed (non-fatal)."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(
                side_effect=httpx.ConnectError("connection refused")
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            # Should not raise
            run_async(client.release_model())


# ── wait_until_ready ─────────────────────────────────────────────────────

class TestWaitUntilReady:
    def test_returns_true_when_immediately_ready(self, client):
        """Ollama responds 200 on first poll → ready immediately."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_instance.get = AsyncMock(return_value=mock_resp)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = run_async(client.wait_until_ready(timeout=5))
            assert result is True

    def test_returns_true_after_retries(self, client):
        """Ollama fails twice then succeeds — should still return True."""
        call_count = 0

        async def eventually_ready(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("not yet")
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            return mock_resp

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=eventually_ready)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = run_async(client.wait_until_ready(timeout=30))
                assert result is True
                assert call_count == 3

    def test_returns_false_on_timeout(self, client):
        """All polls fail → returns False after timeout."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(
                side_effect=httpx.ConnectError("down")
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                # Very short timeout so the test doesn't take long
                result = run_async(client.wait_until_ready(timeout=0))
                assert result is False

    def test_polls_correct_url(self, client):
        """Verifies it polls /api/tags."""
        captured_url = {}

        async def capture_get(url, **kwargs):
            captured_url["url"] = url
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            return mock_resp

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=capture_get)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            run_async(client.wait_until_ready(timeout=5))

        assert captured_url["url"] == "http://localhost:11434/api/tags"


# ── Successful extraction ────────────────────────────────────────────────

class TestSuccessfulExtraction:
    def test_returns_text_and_time(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": '{"po_number": "PO-123"}'}
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = run_async(client.extract_from_image(b"fake_image", "extract"))
            assert "text" in result
            assert "processing_time_ms" in result
            assert result["text"] == '{"po_number": "PO-123"}'

    def test_resets_failure_counter_on_success(self, client):
        client._consecutive_failures = 3
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ok"}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            run_async(client.extract_from_image(b"img", "prompt"))
            assert client._consecutive_failures == 0


# ── Circuit breaker ──────────────────────────────────────────────────────

class TestCircuitBreaker:
    def test_opens_after_5_failures(self, client):
        client._consecutive_failures = 5
        client._last_failure_time = time.time()  # just now

        with pytest.raises(OCRServiceUnavailable, match="circuit breaker"):
            run_async(client.extract_from_image(b"img", "prompt"))

    def test_resets_after_cooldown(self, client):
        client._consecutive_failures = 5
        client._last_failure_time = time.time() - 61  # >60s ago

        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ok"}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = run_async(client.extract_from_image(b"img", "prompt"))
            assert result["text"] == "ok"
            assert client._consecutive_failures == 0

    def test_does_not_open_at_4_failures(self, client):
        client._consecutive_failures = 4
        client._last_failure_time = time.time()

        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ok"}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            # Should NOT raise — breaker threshold is 5
            result = run_async(client.extract_from_image(b"img", "prompt"))
            assert result["text"] == "ok"


# ── Retry and failure ────────────────────────────────────────────────────

class TestRetryBehavior:
    def test_timeout_raises_ocr_timeout_error(self):
        client = OCRClient(
            base_url="http://localhost:11434",
            model="m",
            timeout=1,
            max_retries=2,
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(
                side_effect=httpx.TimeoutException("timed out")
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch.object(client, "wait_until_ready", new_callable=AsyncMock, return_value=True):
                    with pytest.raises(OCRTimeoutError):
                        run_async(client.extract_from_image(b"img", "prompt"))

    def test_http_error_raises_ocr_service_error(self):
        client = OCRClient(
            base_url="http://localhost:11434",
            model="m",
            timeout=1,
            max_retries=2,
        )

        request = httpx.Request("POST", "http://localhost:11434/api/chat")
        response = httpx.Response(500, request=request)

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(
                side_effect=httpx.HTTPStatusError("error", request=request, response=response)
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch.object(client, "wait_until_ready", new_callable=AsyncMock, return_value=True):
                    with patch.object(client, "release_model", new_callable=AsyncMock):
                        with pytest.raises(OCRServiceError):
                            run_async(client.extract_from_image(b"img", "prompt"))

    def test_500_error_triggers_vram_release(self):
        """HTTP 500 errors should call release_model before retrying."""
        client = OCRClient(
            base_url="http://localhost:11434",
            model="m",
            timeout=1,
            max_retries=2,
        )

        request = httpx.Request("POST", "http://localhost:11434/api/chat")
        response = httpx.Response(500, request=request)
        release_calls = 0

        async def track_release():
            nonlocal release_calls
            release_calls += 1

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(
                side_effect=httpx.HTTPStatusError("error", request=request, response=response)
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch.object(client, "wait_until_ready", new_callable=AsyncMock, return_value=True):
                    with patch.object(client, "release_model", side_effect=track_release):
                        with pytest.raises(OCRServiceError):
                            run_async(client.extract_from_image(b"img", "prompt"))

        # release_model called on each 500 error (both attempts)
        assert release_calls == 2

    def test_non_500_error_does_not_release_vram(self):
        """Non-500 HTTP errors should NOT call release_model."""
        client = OCRClient(
            base_url="http://localhost:11434",
            model="m",
            timeout=1,
            max_retries=2,
        )

        request = httpx.Request("POST", "http://localhost:11434/api/chat")
        response = httpx.Response(400, request=request)

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(
                side_effect=httpx.HTTPStatusError("bad request", request=request, response=response)
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch.object(client, "wait_until_ready", new_callable=AsyncMock, return_value=True):
                    with patch.object(client, "release_model", new_callable=AsyncMock) as mock_release:
                        with pytest.raises(OCRServiceError):
                            run_async(client.extract_from_image(b"img", "prompt"))

        mock_release.assert_not_called()

    def test_wait_until_ready_called_between_retries(self):
        """After a failure, wait_until_ready is called before next attempt."""
        client = OCRClient(
            base_url="http://localhost:11434",
            model="m",
            timeout=1,
            max_retries=2,
        )
        ready_calls = 0

        async def track_ready():
            nonlocal ready_calls
            ready_calls += 1
            return True

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=Exception("fail"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch.object(client, "wait_until_ready", side_effect=track_ready):
                    with pytest.raises(OCRServiceError):
                        run_async(client.extract_from_image(b"img", "prompt"))

        # Called once between attempt 0 and attempt 1
        assert ready_calls == 1

    def test_retry_backoff_uses_base_wait(self):
        """Verify retry sleep uses RETRY_BASE_WAIT * (attempt+1)."""
        client = OCRClient(
            base_url="http://localhost:11434",
            model="m",
            timeout=1,
            max_retries=3,
        )
        sleep_times: list[float] = []

        async def track_sleep(duration):
            sleep_times.append(duration)

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=Exception("fail"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with patch("asyncio.sleep", side_effect=track_sleep):
                with patch.object(client, "wait_until_ready", new_callable=AsyncMock, return_value=True):
                    with pytest.raises(OCRServiceError):
                        run_async(client.extract_from_image(b"img", "prompt"))

        # 3 retries → 2 sleep calls: 10*(0+1)=10, 10*(1+1)=20
        assert sleep_times == [10, 20]

    def test_increments_failure_counter_after_all_retries(self):
        client = OCRClient(
            base_url="http://localhost", model="m", timeout=1, max_retries=2
        )
        assert client._consecutive_failures == 0

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=Exception("fail"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch.object(client, "wait_until_ready", new_callable=AsyncMock, return_value=True):
                    with pytest.raises(OCRServiceError):
                        run_async(client.extract_from_image(b"img", "prompt"))

        assert client._consecutive_failures == 1

    def test_records_last_failure_time(self):
        client = OCRClient(
            base_url="http://localhost", model="m", timeout=1, max_retries=1
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=Exception("fail"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            before = time.time()
            with pytest.raises(OCRServiceError):
                run_async(client.extract_from_image(b"img", "prompt"))
            after = time.time()

        assert before <= client._last_failure_time <= after


# ── Payload construction ─────────────────────────────────────────────────

class TestPayload:
    def test_base64_encodes_image(self, client):
        import base64

        captured_payload = {}

        async def capture_post(url, json: dict[str, object] | None = None, **kwargs: object) -> MagicMock:
            if json is not None:
                captured_payload.update(json)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"message": {"content": "ok"}}
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=capture_post)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            run_async(client.extract_from_image(b"test_image_data", "extract this"))

        # Verify base64 encoding
        sent_b64 = captured_payload["messages"][0]["images"][0]
        decoded = base64.b64decode(sent_b64)
        assert decoded == b"test_image_data"

    def test_posts_to_correct_url(self, client):
        captured_url = {}

        async def capture_post(url, **kwargs):
            captured_url["url"] = url
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"message": {"content": "ok"}}
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=capture_post)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            run_async(client.extract_from_image(b"img", "prompt"))

        assert captured_url["url"] == "http://localhost:11434/api/chat"

    def test_uses_configured_model(self, client):
        captured_payload = {}

        async def capture_post(url: str, json: dict[str, object] | None = None, **kwargs: object) -> MagicMock:
            if json is not None:
                captured_payload.update(json)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"message": {"content": "ok"}}
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=capture_post)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            run_async(client.extract_from_image(b"img", "prompt"))

        assert captured_payload["model"] == "glm-ocr"
        assert captured_payload["stream"] is False
        assert captured_payload["options"]["temperature"] == 0.0

    def test_num_predict_is_2048(self, client):
        """num_predict must be 2048 — higher values trigger GGML assertion errors."""
        captured_payload = {}

        async def capture_post(url: str, json: dict[str, object] | None = None, **kwargs: object) -> MagicMock:
            if json is not None:
                captured_payload.update(json)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"message": {"content": "ok"}}
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=capture_post)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            run_async(client.extract_from_image(b"img", "prompt"))

        assert captured_payload["options"]["num_predict"] == 2048
