from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import fitz
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.services.extraction.glm_ocr_client as glm_ocr_client
import app.services.extraction_service as extraction_service
from app.config import Settings, replace_settings
from app.migrations.runner import run
from app.models.document import DocumentRecord
from app.models.order_bundle import OrderBundleRecord
from app.services.extraction.glm_ocr_client import OcrResult
from app.services.extraction.ocr_providers.base import OcrProviderResult
from app.services.extraction.structured_text_parser import FailureCode


_VENDOR_TEXT = (
    "TAX INVOICE\n"
    "Invoice No: ACME/INV/77001\n"
    "Invoice Date: 12-02-2026\n"
    "PO No: PO-77001\n"
    "Taxable Amount: 100000\n"
    "Invoice Total: 118000\n"
)


def _make_blank_pdf(path: Path, *, width: float = 400, height: float = 1000) -> None:
    document = fitz.open()
    document.new_page(width=width, height=height)
    document.save(str(path))
    document.close()


def _ocr_result(text: str, *, provider: str = "glm_ocr", model: str = "glm-ocr:latest") -> OcrResult:
    return OcrResult(
        text=text,
        pages=[{"page_number": 1, "ocr_text_length": len(text)}],
        provider=provider,
        model=model,
        diagnostics={
            "ocr_provider": provider,
            "ocr_model": model,
            "ocr_duration_ms": 20,
            "ocr_text_length": len(text),
            "ocr_pages_attempted": 1,
            "ocr_page_results": [{"page_number": 1, "ocr_text_length": len(text)}],
        },
    )


def _paddle_result(
    *,
    success: bool,
    raw_text: str = "",
    error: str | None = None,
    duration_ms: int = 100,
    provider_name: str = "paddleocr_gpu",
) -> OcrProviderResult:
    return OcrProviderResult(
        provider_name=provider_name,
        source_type="ocr",
        raw_text=raw_text,
        success=success,
        error=error,
        duration_ms=duration_ms,
        model=None,
    )


def _mock_paddle_provider(*, available: bool = True, result: OcrProviderResult | None = None) -> MagicMock:
    provider = MagicMock()
    provider.provider_name = "paddleocr_gpu"
    provider.is_available.return_value = available
    if result is not None:
        provider.run_full_page.return_value = result
    return provider


def _make_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    *,
    ocr_provider: str = "glm_ocr",
    ocr_paddle_fallback_to_glm: bool = True,
    ocr_enabled: bool = True,
) -> Session:
    db_url = f"sqlite:///{tmp_path / name}"
    current = Settings(
        database_url=db_url,
        evidence_capture_enabled=False,
        digital_text_enabled=True,
        structured_rules_enabled=True,
        ocr_enabled=ocr_enabled,
        ocr_provider=ocr_provider,
        ocr_model="glm-ocr:latest",
        model_layer2_enabled=False,
        ocr_paddle_device="gpu:0",
        ocr_paddle_timeout_seconds=60,
        ocr_paddle_fallback_to_glm=ocr_paddle_fallback_to_glm,
    )
    replace_settings(current)
    monkeypatch.setattr(extraction_service, "settings", current)
    monkeypatch.setattr(glm_ocr_client, "settings", current)
    run("up")
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _setup_document(
    db: Session,
    storage_path: str,
    *,
    document_type: str = "VENDOR_INVOICE",
    filename: str = "Vendor Invoice Document.pdf",
) -> DocumentRecord:
    now = datetime.now(timezone.utc)
    bundle = OrderBundleRecord(
        id=str(uuid4()),
        bundle_number=f"ROUTING-{uuid4().hex[:8]}",
        created_at=now,
        updated_at=now,
    )
    db.add(bundle)
    db.flush()
    document = DocumentRecord(
        id=str(uuid4()),
        order_bundle_id=bundle.id,
        document_type=document_type,
        filename=filename,
        storage_path=storage_path,
        status="UPLOADED",
        created_at=now,
        updated_at=now,
    )
    db.add(document)
    db.flush()
    return document


# ---------------------------------------------------------------------------
# 1. Default config / no env uses existing GLM path.
# ---------------------------------------------------------------------------
def test_default_config_uses_glm_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdf = tmp_path / "vendor.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "default.db")
    document = _setup_document(db, str(pdf))

    with patch.object(extraction_service, "extract_text_with_ocr", return_value=_ocr_result(_VENDOR_TEXT)) as glm_mock:
        result = extraction_service.extract_document(db, document, force=True)

    glm_mock.assert_called_once()
    assert result["metadata"].diagnostics["ocr_route"] == "glm"
    assert result["metadata"].diagnostics["extraction_route"] == "ocr_glm"
    assert result["metadata"].extracted_data["vendor_invoice_no"] == "ACME/INV/77001"


# ---------------------------------------------------------------------------
# 2. Default path does not instantiate PaddleOcrProvider.
# ---------------------------------------------------------------------------
def test_default_path_does_not_instantiate_paddle_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdf = tmp_path / "vendor.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "no_paddle.db")
    document = _setup_document(db, str(pdf))

    with (
        patch.object(extraction_service, "extract_text_with_ocr", return_value=_ocr_result(_VENDOR_TEXT)),
        patch.object(extraction_service, "PaddleOcrProvider") as paddle_cls,
    ):
        extraction_service.extract_document(db, document, force=True)

    paddle_cls.assert_not_called()


# ---------------------------------------------------------------------------
# 3. OCR_PROVIDER=glm uses existing GLM path.
# ---------------------------------------------------------------------------
def test_ocr_provider_glm_alias_uses_glm_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdf = tmp_path / "vendor.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "alias.db", ocr_provider="glm")
    document = _setup_document(db, str(pdf))

    with patch.object(extraction_service, "extract_text_with_ocr", return_value=_ocr_result(_VENDOR_TEXT)) as glm_mock:
        result = extraction_service.extract_document(db, document, force=True)

    glm_mock.assert_called_once()
    assert result["metadata"].diagnostics["ocr_route"] == "glm"
    assert result["metadata"].extracted_data["vendor_invoice_no"] == "ACME/INV/77001"


# ---------------------------------------------------------------------------
# 4. OCR_PROVIDER=paddleocr_gpu + VENDOR_INVOICE instantiates PaddleOcrProvider
#    with device="gpu:0" and enforce_timeout=True.
# ---------------------------------------------------------------------------
def test_paddle_route_instantiates_provider_with_gpu_and_enforce_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdf = tmp_path / "vendor.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "paddle_instantiate.db", ocr_provider="paddleocr_gpu")
    document = _setup_document(db, str(pdf))

    provider = _mock_paddle_provider(result=_paddle_result(success=True, raw_text=_VENDOR_TEXT))

    with (
        patch.object(extraction_service, "PaddleOcrProvider", return_value=provider) as paddle_cls,
        patch.object(extraction_service, "extract_text_with_ocr") as glm_mock,
    ):
        extraction_service.extract_document(db, document, force=True)

    paddle_cls.assert_called_once_with(device="gpu:0", enforce_timeout=True)
    glm_mock.assert_not_called()


# ---------------------------------------------------------------------------
# 5. PaddleOCR successful result is parsed with the existing parser.
# ---------------------------------------------------------------------------
def test_paddle_success_result_is_parsed_with_existing_parser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdf = tmp_path / "vendor.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "paddle_parsed.db", ocr_provider="paddleocr_gpu")
    document = _setup_document(db, str(pdf))

    provider = _mock_paddle_provider(result=_paddle_result(success=True, raw_text=_VENDOR_TEXT))

    with patch.object(extraction_service, "PaddleOcrProvider", return_value=provider):
        result = extraction_service.extract_document(db, document, force=True)

    fields = result["metadata"].extracted_data
    assert fields["vendor_invoice_no"] == "ACME/INV/77001"
    assert fields["vendor_invoice_date"] == "12-02-2026"
    assert fields["po_reference"] == "PO-77001"
    assert result["metadata"].diagnostics["extraction_route"] == "ocr_paddleocr_gpu"
    assert result["metadata"].diagnostics["ocr_route"] == "paddleocr_gpu"
    assert result["metadata"].diagnostics["ocr_provider"] == "paddleocr_gpu"


# ---------------------------------------------------------------------------
# 6. PaddleOCR successful result does not call GLM.
# ---------------------------------------------------------------------------
def test_paddle_success_does_not_call_glm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdf = tmp_path / "vendor.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "paddle_no_glm.db", ocr_provider="paddleocr_gpu")
    document = _setup_document(db, str(pdf))

    provider = _mock_paddle_provider(result=_paddle_result(success=True, raw_text=_VENDOR_TEXT))

    with (
        patch.object(extraction_service, "PaddleOcrProvider", return_value=provider),
        patch.object(extraction_service, "extract_text_with_ocr") as glm_mock,
    ):
        extraction_service.extract_document(db, document, force=True)

    glm_mock.assert_not_called()


# ---------------------------------------------------------------------------
# 7. PaddleOCR unavailable with fallback enabled calls GLM.
# ---------------------------------------------------------------------------
def test_paddle_unavailable_with_fallback_calls_glm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdf = tmp_path / "vendor.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "paddle_unavailable.db", ocr_provider="paddleocr_gpu", ocr_paddle_fallback_to_glm=True)
    document = _setup_document(db, str(pdf))

    provider = _mock_paddle_provider(available=False)

    with (
        patch.object(extraction_service, "PaddleOcrProvider", return_value=provider),
        patch.object(extraction_service, "extract_text_with_ocr", return_value=_ocr_result(_VENDOR_TEXT)) as glm_mock,
    ):
        result = extraction_service.extract_document(db, document, force=True)

    glm_mock.assert_called_once()
    provider.run_full_page.assert_not_called()
    assert result["metadata"].diagnostics["ocr_route"] == "paddleocr_gpu_then_glm_fallback"
    assert result["metadata"].extracted_data["vendor_invoice_no"] == "ACME/INV/77001"


# ---------------------------------------------------------------------------
# 8. PaddleOCR timeout/failure with fallback enabled calls GLM.
# ---------------------------------------------------------------------------
def test_paddle_timeout_with_fallback_calls_glm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdf = tmp_path / "vendor.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "paddle_timeout.db", ocr_provider="paddleocr_gpu", ocr_paddle_fallback_to_glm=True)
    document = _setup_document(db, str(pdf))

    provider = _mock_paddle_provider(
        result=_paddle_result(success=False, error="PaddleOCR subprocess timed out after 60s")
    )

    with (
        patch.object(extraction_service, "PaddleOcrProvider", return_value=provider),
        patch.object(extraction_service, "extract_text_with_ocr", return_value=_ocr_result(_VENDOR_TEXT)) as glm_mock,
    ):
        result = extraction_service.extract_document(db, document, force=True)

    glm_mock.assert_called_once()
    assert result["metadata"].diagnostics["ocr_route"] == "paddleocr_gpu_then_glm_fallback"
    assert "timed out" in result["metadata"].diagnostics["ocr_paddle_error"]
    assert result["metadata"].extracted_data["vendor_invoice_no"] == "ACME/INV/77001"


# ---------------------------------------------------------------------------
# 9. PaddleOCR empty text with fallback enabled calls GLM.
# ---------------------------------------------------------------------------
def test_paddle_empty_text_with_fallback_calls_glm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdf = tmp_path / "vendor.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "paddle_empty.db", ocr_provider="paddleocr_gpu", ocr_paddle_fallback_to_glm=True)
    document = _setup_document(db, str(pdf))

    provider = _mock_paddle_provider(result=_paddle_result(success=True, raw_text="   "))

    with (
        patch.object(extraction_service, "PaddleOcrProvider", return_value=provider),
        patch.object(extraction_service, "extract_text_with_ocr", return_value=_ocr_result(_VENDOR_TEXT)) as glm_mock,
    ):
        result = extraction_service.extract_document(db, document, force=True)

    glm_mock.assert_called_once()
    assert result["metadata"].diagnostics["ocr_route"] == "paddleocr_gpu_then_glm_fallback"
    assert result["metadata"].extracted_data["vendor_invoice_no"] == "ACME/INV/77001"


# ---------------------------------------------------------------------------
# 10. PaddleOCR failure with fallback disabled returns controlled failure result.
# ---------------------------------------------------------------------------
def test_paddle_failure_without_fallback_returns_controlled_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdf = tmp_path / "vendor.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "paddle_no_fallback.db", ocr_provider="paddleocr_gpu", ocr_paddle_fallback_to_glm=False)
    document = _setup_document(db, str(pdf))

    provider = _mock_paddle_provider(result=_paddle_result(success=False, error="boom"))

    with (
        patch.object(extraction_service, "PaddleOcrProvider", return_value=provider),
        patch.object(extraction_service, "extract_text_with_ocr") as glm_mock,
    ):
        result = extraction_service.extract_document(db, document, force=True)

    glm_mock.assert_not_called()
    diagnostics = result["metadata"].diagnostics
    assert diagnostics["ocr_route"] == "paddleocr_gpu"
    assert diagnostics["failure_code"] == FailureCode.OCR_FAILED.value
    assert "paddleocr_gpu" in diagnostics["failure_reason"]
    assert "boom" in diagnostics["failure_reason"]
    assert result["metadata"].status in {"FAILED", "MANUAL_ENTRY"}


# ---------------------------------------------------------------------------
# 11. Non-VENDOR_INVOICE document still uses GLM even if OCR_PROVIDER=paddleocr_gpu.
# ---------------------------------------------------------------------------
def test_non_vendor_invoice_uses_glm_even_with_paddle_provider_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdf = tmp_path / "company_invoice.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "non_vendor.db", ocr_provider="paddleocr_gpu")
    document = _setup_document(db, str(pdf), document_type="COMPANY_INVOICE", filename="Company Invoice.pdf")

    with (
        patch.object(extraction_service, "extract_text_with_ocr", return_value=_ocr_result(_VENDOR_TEXT)) as glm_mock,
        patch.object(extraction_service, "PaddleOcrProvider") as paddle_cls,
    ):
        result = extraction_service.extract_document(db, document, force=True)

    glm_mock.assert_called_once()
    paddle_cls.assert_not_called()
    assert result["metadata"].diagnostics["ocr_route"] == "glm"
    assert result["metadata"].diagnostics["extraction_route"] == "ocr_glm"


# ---------------------------------------------------------------------------
# 12. GLM remains the default provider when no config is set.
# ---------------------------------------------------------------------------
def test_default_settings_ocr_provider_is_glm_ocr():
    assert Settings().ocr_provider == "glm_ocr"


# ---------------------------------------------------------------------------
# 13. No hardcoded Panimalar/AMC/Trade values in extraction_service.
# ---------------------------------------------------------------------------
def test_no_hardcoded_panimalar_values_in_extraction_service():
    source = inspect.getsource(extraction_service).lower()
    assert "panimalar" not in source
    assert "amc" not in source
    assert "trade" not in source
