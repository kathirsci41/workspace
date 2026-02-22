"""Unit tests for the TwoLayerClient (OCR cleanup, JSON parsing, orchestration)."""
import json
import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.extraction.two_layer_client import TwoLayerClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    return TwoLayerClient(
        base_url="http://localhost:11434",
        ocr_model="glm-ocr:latest",
        extractor_model="qwen2.5:7b",
        timeout=30,
        max_retries=1,
        save_debug_markdown=False,
    )


# ---------------------------------------------------------------------------
# _clean_ocr_output — GLM artifact removal
# ---------------------------------------------------------------------------
class TestCleanOcrOutput:
    def test_removes_repetitive_blank_rows(self, client):
        # GLM-OCR in grounding mode outputs HTML; blank rows are empty <tr> elements
        blank_row = "<tr><td></td><td></td></tr>"
        text = f"<table>{blank_row * 4}</table>"
        cleaned = client._clean_ocr_output(text)
        assert blank_row not in cleaned

    def test_compresses_excessive_blank_lines(self, client):
        text = "Line1\n\n\n\n\n\nLine2"
        cleaned = client._clean_ocr_output(text)
        assert cleaned == "Line1\n\nLine2"

    def test_fixes_11TR_inline(self, client):
        text = "Invoice: 11TR2526001841 total"
        cleaned = client._clean_ocr_output(text)
        assert "1ITR2526001841" in cleaned

    def test_fixes_11SR_inline(self, client):
        text = "Ref: 11SR2526000166"
        cleaned = client._clean_ocr_output(text)
        assert "1ISR2526000166" in cleaned

    def test_strips_whitespace(self, client):
        text = "   content   "
        cleaned = client._clean_ocr_output(text)
        assert cleaned == "content"

    def test_preserves_valid_table(self, client):
        text = "| Col1 | Col2 |\n| --- | --- |\n| Val1 | Val2 |"
        cleaned = client._clean_ocr_output(text)
        assert "Val1" in cleaned
        assert "Val2" in cleaned


# ---------------------------------------------------------------------------
# _parse_json_safe — multi-strategy JSON extraction
# ---------------------------------------------------------------------------
class TestParseJsonSafe:
    def test_direct_json(self, client):
        text = '{"invoice_number": "INV-001", "total_amount": 1500}'
        result = client._parse_json_safe(text)
        assert result["invoice_number"] == "INV-001"
        assert result["total_amount"] == 1500

    def test_json_code_block(self, client):
        text = '```json\n{"dc_number": "DC-100"}\n```'
        result = client._parse_json_safe(text)
        assert result["dc_number"] == "DC-100"

    def test_generic_code_block(self, client):
        text = '```\n{"dc_number": "DC-100"}\n```'
        result = client._parse_json_safe(text)
        assert result["dc_number"] == "DC-100"

    def test_json_with_surrounding_text(self, client):
        text = 'Here is the result: {"po_number": "PO-999"} done.'
        result = client._parse_json_safe(text)
        assert result["po_number"] == "PO-999"

    def test_trailing_comma_cleaned(self, client):
        text = '{"a": 1, "b": 2,}'
        result = client._parse_json_safe(text)
        assert result == {"a": 1, "b": 2}

    def test_garbage_returns_empty_dict(self, client):
        result = client._parse_json_safe("this is not json at all")
        assert result == {}

    def test_empty_string_returns_empty_dict(self, client):
        result = client._parse_json_safe("")
        assert result == {}


# ---------------------------------------------------------------------------
# _clean_json — common LLM JSON issues
# ---------------------------------------------------------------------------
class TestCleanJson:
    def test_trailing_comma_before_brace(self):
        assert TwoLayerClient._clean_json('{"a": 1,}') == '{"a": 1}'

    def test_trailing_comma_before_bracket(self):
        assert TwoLayerClient._clean_json('[1, 2,]') == '[1, 2]'

    def test_control_chars_removed(self):
        text = '{"a":\x00"b"}'
        cleaned = TwoLayerClient._clean_json(text)
        assert "\x00" not in cleaned

    def test_comma_formatted_numbers(self):
        text = '{"total": 86,678.50}'
        cleaned = TwoLayerClient._clean_json(text)
        parsed = json.loads(cleaned)
        assert parsed["total"] == 86678.5


# ---------------------------------------------------------------------------
# Circuit breaker behavior
# ---------------------------------------------------------------------------
class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_opens_after_5_failures(self, client):
        client._consecutive_failures = 5
        client._last_failure_time = time.time()

        with pytest.raises(RuntimeError, match="(?i)circuit breaker open"):
            await client._call_ollama_generate({"model": "test"})

    @pytest.mark.asyncio
    async def test_resets_after_cooldown(self, client):
        client._consecutive_failures = 5
        client._last_failure_time = time.time() - 120  # well past cooldown

        # It will still fail on the actual HTTP call, but it should NOT
        # raise the circuit-breaker error
        with pytest.raises(RuntimeError, match="failed after"):
            await client._call_ollama_generate({"model": "test"})


# ---------------------------------------------------------------------------
# extract — orchestration (mocked HTTP)
# ---------------------------------------------------------------------------
class TestExtract:
    @pytest.mark.asyncio
    async def test_empty_ocr_returns_empty_fields(self, client):
        """When Layer 1 returns near-empty text, skip Layer 2."""
        client._run_ocr_layer = AsyncMock(return_value=("", 50))

        result = await client.extract(b"fake_image", "COMPANY_DC", "page1")

        assert result["fields"] == {}
        assert result["text"] == ""
        assert result["ocr_ms"] == 50

    @pytest.mark.asyncio
    async def test_short_ocr_returns_empty_fields(self, client):
        """OCR text under 20 chars should short-circuit."""
        client._run_ocr_layer = AsyncMock(return_value=("short", 30))

        result = await client.extract(b"fake_image", "COMPANY_DC", "page1")

        assert result["fields"] == {}

    @pytest.mark.asyncio
    async def test_full_pipeline_success(self, client):
        """Happy path: OCR returns markdown, extraction returns fields."""
        markdown = "# Invoice\nInvoice No: 1ITR2526001841\nTotal: 50000"
        fields = {"invoice_number": "1ITR2526001841", "total_amount": 50000}

        client._run_ocr_layer = AsyncMock(return_value=(markdown, 500))
        client._run_extraction_layer = AsyncMock(return_value=(fields, 300))
        client.release_model = AsyncMock()

        result = await client.extract(
            b"fake_image", "VENDOR_INVOICE", "page1"
        )

        assert result["fields"]["invoice_number"] == "1ITR2526001841"
        assert result["fields"]["total_amount"] == 50000.0
        assert result["ocr_ms"] == 500
        assert result["extract_ms"] == 300
        assert result["total_ms"] > 0

        # Verify VRAM was released between layers
        client.release_model.assert_called_once_with("glm-ocr:latest")

    @pytest.mark.asyncio
    async def test_validation_applied_to_fields(self, client):
        """Extracted fields should pass through validate_extracted_fields."""
        markdown = "# DC\nDC No: lDNT2526DC001841\nPO Ref: Rajesh Kumar"
        fields = {
            "dc_number": "lDNT2526DC001841",
            "po_reference": "Rajesh Kumar",
        }

        client._run_ocr_layer = AsyncMock(return_value=(markdown, 400))
        client._run_extraction_layer = AsyncMock(return_value=(fields, 200))
        client.release_model = AsyncMock()

        result = await client.extract(b"fake_image", "COMPANY_DC", "page1")

        # DC number should be corrected
        assert result["fields"]["dc_number"] == "1DNT2526DC001841"
        # Person name should be rejected
        assert result["fields"]["po_reference"] is None
        assert "_validation" in result["fields"]


# ---------------------------------------------------------------------------
# wait_until_ready
# ---------------------------------------------------------------------------
class TestWaitUntilReady:
    @pytest.mark.asyncio
    async def test_returns_true_when_ollama_responds(self, client):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await client.wait_until_ready(timeout=5)
            assert result is True
