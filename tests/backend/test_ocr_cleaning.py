"""
Unit tests for TwoLayerClient._clean_ocr_output.

Verifies all OCR artifact corrections:
  - HTML entity unescaping
  - Empty table row removal
  - Date format fixing
  - I/1 confusion (11TR → 1ITR)
  - O/0 confusion (10TM → 1OTM)
  - D/0 + N/T transposition (10TN → 1DNT)
  - Spurious Z in SO numbers (1OTMZ → 1OTM)
  - Spurious digit in bill numbers (1PBT2R → 1PBTR)
  - T/F confusion in PO numbers (1PFR → 1PTR)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

import pytest
from app.services.extraction.two_layer_client import TwoLayerClient


@pytest.fixture
def client():
    return TwoLayerClient(base_url="http://localhost:11434")


class TestHtmlEntityUnescaping:

    def test_amp_unescaped(self, client):
        assert "&" in client._clean_ocr_output("Company &amp; Sons")

    def test_lt_gt_unescaped(self, client):
        result = client._clean_ocr_output("&lt;value&gt;")
        assert "<value>" in result

    def test_no_entities_unchanged(self, client):
        text = "Plain text with no entities"
        assert client._clean_ocr_output(text) == text


class TestEmptyTableRowRemoval:

    def test_three_empty_rows_removed(self, client):
        empty_row = "<tr><td></td><td></td></tr>"
        text = "before\n" + (empty_row + "\n") * 3 + "after"
        result = client._clean_ocr_output(text)
        assert result.count("<tr>") == 0

    def test_two_empty_rows_kept(self, client):
        """Fewer than 3 repeated empty rows should NOT be removed."""
        empty_row = "<tr><td></td></tr>"
        text = empty_row + "\n" + empty_row
        result = client._clean_ocr_output(text)
        assert result.count("<tr>") == 2

    def test_data_rows_not_removed(self, client):
        text = "<tr><td>Item</td><td>100</td></tr>"
        result = client._clean_ocr_output(text)
        assert "<tr>" in result


class TestDateFixing:

    def test_missing_slash_in_date(self, client):
        """1812/2025 → 18/12/2025 (OCR drops first slash)."""
        result = client._clean_ocr_output("Date: 1812/2025")
        assert "18/12/2025" in result

    def test_normal_date_unchanged(self, client):
        result = client._clean_ocr_output("Date: 18/12/2025")
        assert "18/12/2025" in result


class TestIvs1Confusion:

    def test_11TR_to_1ITR(self, client):
        result = client._clean_ocr_output("DC No: 11TR2526001841")
        assert "1ITR2526001841" in result

    def test_11SR_to_1ISR(self, client):
        result = client._clean_ocr_output("Ref: 11SR2526001234")
        assert "1ISR2526001234" in result

    def test_IT1R_to_1ITR(self, client):
        result = client._clean_ocr_output("DC: IT1R2526001234")
        assert "1ITR2526001234" in result

    def test_IT1SR_to_1ISR(self, client):
        result = client._clean_ocr_output("Ref: IT1SR2526001234")
        assert "1ISR2526001234" in result

    def test_correct_1ITR_unchanged(self, client):
        result = client._clean_ocr_output("DC No: 1ITR2526001841")
        assert "1ITR2526001841" in result


class TestOvs0Confusion:

    def test_10TM_to_1OTM(self, client):
        result = client._clean_ocr_output("SO: 10TM2526001234")
        assert "1OTM2526001234" in result

    def test_correct_1OTM_unchanged(self, client):
        result = client._clean_ocr_output("SO: 1OTM2526001234")
        assert "1OTM2526001234" in result

    def test_1OTMZ_spurious_Z_removed(self, client):
        result = client._clean_ocr_output("SO: 1OTMZ2526001234")
        assert "1OTM2526001234" in result


class TestDCNumberFixing:

    def test_10TN_to_1DNT(self, client):
        result = client._clean_ocr_output("DC: 10TN2526001234")
        assert "1DNT2526001234" in result

    def test_10NT_to_1DNT(self, client):
        result = client._clean_ocr_output("DC: 10NT2526001234")
        assert "1DNT2526001234" in result


class TestPurchaseBillFixing:

    def test_1PBT2R_to_1PBTR(self, client):
        result = client._clean_ocr_output("Bill: 1PBT2R2526001234")
        assert "1PBTR2526001234" in result

    def test_1PFR_to_1PTR(self, client):
        result = client._clean_ocr_output("PO: 1PFR2526001234")
        assert "1PTR2526001234" in result


class TestExcessiveBlankLines:

    def test_four_newlines_reduced_to_two(self, client):
        result = client._clean_ocr_output("line1\n\n\n\n\nline2")
        assert "\n\n\n" not in result
        assert "line1" in result
        assert "line2" in result