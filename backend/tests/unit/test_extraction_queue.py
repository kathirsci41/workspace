from __future__ import annotations

import threading
import time

import pytest

from app.services.extraction_queue import (
    OcrExtractionQueue,
    OcrExtractionQueueTimeoutError,
)


def test_two_ocr_jobs_are_serialized_and_second_waits():
    queue = OcrExtractionQueue()
    entered: list[str] = []
    first_entered = threading.Event()
    release_first = threading.Event()

    def first_job() -> None:
        with queue.acquire(
            document_id="doc-1",
            filename="first.pdf",
            provider="glm_ocr",
            enabled=True,
            max_concurrent=1,
            max_size=10,
            timeout_seconds=5,
        ):
            entered.append("first")
            first_entered.set()
            assert release_first.wait(timeout=2)

    def second_job() -> None:
        assert first_entered.wait(timeout=2)
        with queue.acquire(
            document_id="doc-2",
            filename="second.pdf",
            provider="glm_ocr",
            enabled=True,
            max_concurrent=1,
            max_size=10,
            timeout_seconds=5,
        ) as diagnostics:
            entered.append("second")
            assert diagnostics["queued"] is True
            assert diagnostics["queue_wait_ms"] > 0

    first = threading.Thread(target=first_job)
    second = threading.Thread(target=second_job)
    first.start()
    second.start()

    assert first_entered.wait(timeout=2)
    time.sleep(0.05)
    assert entered == ["first"]
    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert entered == ["first", "second"]
    assert queue.activity()["active"] is False


def test_queue_slot_releases_after_success():
    queue = OcrExtractionQueue()

    with queue.acquire(
        document_id="doc-1",
        filename="success.pdf",
        provider="glm_ocr",
        enabled=True,
        max_concurrent=1,
        max_size=10,
        timeout_seconds=5,
    ) as diagnostics:
        assert diagnostics["queued"] is False
        assert queue.activity()["active"] is True

    assert queue.activity()["active"] is False


def test_queue_slot_releases_after_exception():
    queue = OcrExtractionQueue()

    with pytest.raises(RuntimeError, match="ocr failed"):
        with queue.acquire(
            document_id="doc-1",
            filename="failure.pdf",
            provider="glm_ocr",
            enabled=True,
            max_concurrent=1,
            max_size=10,
            timeout_seconds=5,
        ):
            raise RuntimeError("ocr failed")

    assert queue.activity()["active"] is False


def test_queue_timeout_returns_clean_error_and_removes_waiter():
    queue = OcrExtractionQueue()
    release_first = threading.Event()

    def first_job() -> None:
        with queue.acquire(
            document_id="doc-1",
            filename="first.pdf",
            provider="glm_ocr",
            enabled=True,
            max_concurrent=1,
            max_size=10,
            timeout_seconds=5,
        ):
            assert release_first.wait(timeout=2)

    first = threading.Thread(target=first_job)
    first.start()
    time.sleep(0.05)

    with pytest.raises(OcrExtractionQueueTimeoutError) as exc_info:
        with queue.acquire(
            document_id="doc-2",
            filename="second.pdf",
            provider="glm_ocr",
            enabled=True,
            max_concurrent=1,
            max_size=10,
            timeout_seconds=0.05,
        ):
            pass

    assert "Timed out waiting for OCR extraction queue" in str(exc_info.value)
    activity = queue.activity()
    assert activity["queue_count"] == 0
    assert activity["active_jobs"][0]["filename"] == "first.pdf"

    release_first.set()
    first.join(timeout=2)
    assert queue.activity()["active"] is False

