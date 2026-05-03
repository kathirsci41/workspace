"""Security test: item_matcher must never create an httpx.AsyncClient with verify=False."""
import asyncio
import json
import pytest

from unittest.mock import AsyncMock, MagicMock, patch


def run_async(coro):
    return asyncio.run(coro)


def _make_mock_response(payload: list[dict]) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "message": {"content": json.dumps(payload)}
    }
    return mock_resp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CUSTOMER_ITEMS = [{"sr_no": 1, "description": "Widget A"}]
COMPANY_ITEMS  = [{"sr_no": 1, "part_no": "WA-001", "description": "Widget A Pro"}]


def _run_llm_match_with_settings(ca_bundle_value):
    """
    Invoke _llm_match with a patched settings.ocr_extractor_ca_bundle and
    capture the kwargs passed to httpx.AsyncClient.
    """
    captured_kwargs: list[dict] = []

    class _FakeClient:
        def __init__(self, **kwargs):
            captured_kwargs.append(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, url, **kwargs):
            return _make_mock_response([
                {"sr_no": 1, "matched_part_no": "WA-001", "confidence": 0.9}
            ])

    with patch("app.services.item_matcher.settings") as mock_settings, \
         patch("app.services.item_matcher.httpx.AsyncClient", _FakeClient):

        mock_settings.ocr_extractor_ca_bundle = ca_bundle_value
        mock_settings.ocr_extractor_base_url = "https://llm.example.com"
        mock_settings.ocr_base_url = "http://localhost:11434"
        mock_settings.ocr_extractor_model = "qwen2.5:7b"

        from app.services import item_matcher
        run_async(item_matcher._llm_match(CUSTOMER_ITEMS, COMPANY_ITEMS))

    return captured_kwargs


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestItemMatcherTLS:

    def test_verify_is_true_when_ca_bundle_not_set(self):
        """Default config (no CA bundle) must use verify=True (system trust store)."""
        kwargs_list = _run_llm_match_with_settings(None)
        assert kwargs_list, "httpx.AsyncClient was never instantiated"
        verify = kwargs_list[0].get("verify")
        assert verify is not False, (
            "httpx.AsyncClient must NOT be created with verify=False — "
            f"got verify={verify!r}"
        )
        assert verify is True, f"Expected verify=True, got verify={verify!r}"

    def test_verify_is_true_when_ca_bundle_is_empty_string(self):
        """Empty-string ca_bundle is falsy — should fall back to verify=True."""
        kwargs_list = _run_llm_match_with_settings("")
        assert kwargs_list, "httpx.AsyncClient was never instantiated"
        verify = kwargs_list[0].get("verify")
        assert verify is not False, (
            f"httpx.AsyncClient must NOT be created with verify=False — got verify={verify!r}"
        )

    def test_verify_uses_ca_bundle_path_when_set(self):
        """When a CA bundle path is configured, verify must equal that path."""
        bundle = "/etc/ssl/certs/custom-ca.crt"
        kwargs_list = _run_llm_match_with_settings(bundle)
        assert kwargs_list, "httpx.AsyncClient was never instantiated"
        verify = kwargs_list[0].get("verify")
        assert verify == bundle, (
            f"Expected verify={bundle!r}, got verify={verify!r}"
        )
        assert verify is not False

    def test_verify_false_not_present_in_any_call(self):
        """Regression guard: verify=False must never appear regardless of ca_bundle value."""
        for ca_bundle in (None, "", "/some/path.crt"):
            kwargs_list = _run_llm_match_with_settings(ca_bundle)
            for kwargs in kwargs_list:
                assert kwargs.get("verify") is not False, (
                    f"verify=False detected when ca_bundle={ca_bundle!r}"
                )
