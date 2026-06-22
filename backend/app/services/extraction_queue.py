from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
import time
from uuid import uuid4


class OcrExtractionQueueTimeoutError(TimeoutError):
    pass


class OcrExtractionQueueFullError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class _QueueJob:
    id: str
    document_id: str
    filename: str
    provider: str
    status: str = "queued"
    queued_at: str = field(default_factory=_now_iso)
    started_at: str | None = None
    finished_at: str | None = None
    queue_position: int | None = None
    active_filename: str | None = None


class OcrExtractionQueue:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._queued: deque[_QueueJob] = deque()
        self._active: dict[str, _QueueJob] = {}

    @contextmanager
    def acquire(
        self,
        *,
        document_id: str,
        filename: str,
        provider: str,
        enabled: bool,
        max_concurrent: int,
        max_size: int,
        timeout_seconds: float,
    ) -> Iterator[dict[str, object]]:
        if not enabled:
            diagnostics: dict[str, object] = {
                "queued": False,
                "queue_position": None,
                "queue_wait_ms": 0,
                "queue_timeout_used": timeout_seconds,
                "extraction_started_at": _now_iso(),
                "extraction_finished_at": None,
                "active_filename": None,
                "provider": provider,
            }
            try:
                yield diagnostics
            finally:
                diagnostics["extraction_finished_at"] = _now_iso()
            return

        max_concurrent = max(1, int(max_concurrent))
        max_size = max(0, int(max_size))
        timeout_seconds = max(0.001, float(timeout_seconds))
        job = _QueueJob(
            id=str(uuid4()),
            document_id=document_id,
            filename=filename,
            provider=provider,
        )
        wait_started = time.perf_counter()
        queued = False

        with self._condition:
            if self._can_start(max_concurrent):
                self._start_job(job)
            else:
                if len(self._queued) >= max_size:
                    raise OcrExtractionQueueFullError("OCR extraction queue is full.")
                queued = True
                job.queue_position = len(self._queued) + 1
                job.active_filename = self._first_active_filename()
                self._queued.append(job)
                self._condition.notify_all()
                deadline = time.perf_counter() + timeout_seconds
                while True:
                    if self._queued and self._queued[0] is job and self._can_start(max_concurrent):
                        self._queued.popleft()
                        self._start_job(job)
                        break
                    remaining = deadline - time.perf_counter()
                    if remaining <= 0:
                        self._remove_queued_job(job)
                        self._condition.notify_all()
                        raise OcrExtractionQueueTimeoutError(
                            f"Timed out waiting for OCR extraction queue after {timeout_seconds:g}s."
                        )
                    self._condition.wait(remaining)

        diagnostics = {
            "queued": queued,
            "queue_position": job.queue_position if queued else None,
            "queue_wait_ms": round((time.perf_counter() - wait_started) * 1000, 2),
            "queue_timeout_used": timeout_seconds,
            "extraction_started_at": job.started_at,
            "extraction_finished_at": None,
            "active_filename": job.active_filename,
            "provider": provider,
        }
        try:
            yield diagnostics
        finally:
            finished_at = _now_iso()
            with self._condition:
                self._active.pop(job.id, None)
                job.status = "finished"
                job.finished_at = finished_at
                self._condition.notify_all()
            diagnostics["extraction_finished_at"] = finished_at

    def activity(self) -> dict[str, object]:
        with self._condition:
            active_jobs = [_job_to_activity(job) for job in self._active.values()]
            queued_jobs = [
                _job_to_activity(job, queue_position=index)
                for index, job in enumerate(self._queued, start=1)
            ]
        return {
            "active": bool(active_jobs or queued_jobs),
            "active_count": len(active_jobs),
            "queue_count": len(queued_jobs),
            "active_jobs": active_jobs,
            "queued_jobs": queued_jobs,
        }

    def reset_for_tests(self) -> None:
        with self._condition:
            self._queued.clear()
            self._active.clear()
            self._condition.notify_all()

    def _can_start(self, max_concurrent: int) -> bool:
        return len(self._active) < max_concurrent

    def _start_job(self, job: _QueueJob) -> None:
        job.status = "running"
        job.started_at = _now_iso()
        self._active[job.id] = job
        self._condition.notify_all()

    def _remove_queued_job(self, job: _QueueJob) -> None:
        self._queued = deque(entry for entry in self._queued if entry is not job)

    def _first_active_filename(self) -> str | None:
        for job in self._active.values():
            return job.filename
        return None


ocr_extraction_queue = OcrExtractionQueue()


def get_ocr_extraction_activity() -> dict[str, object]:
    return ocr_extraction_queue.activity()


def _job_to_activity(job: _QueueJob, *, queue_position: int | None = None) -> dict[str, object]:
    started_at = job.started_at or job.queued_at
    return {
        "id": job.id,
        "document_id": job.document_id,
        "filename": job.filename,
        "provider": job.provider,
        "status": job.status,
        "stage": "Waiting in extraction queue" if job.status == "queued" else "Running OCR",
        "queued_at": job.queued_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "queue_position": queue_position if queue_position is not None else job.queue_position,
        "elapsed_ms": _elapsed_ms(started_at),
    }


def _elapsed_ms(started_at: str | None) -> int:
    if not started_at:
        return 0
    try:
        started = datetime.fromisoformat(started_at)
    except ValueError:
        return 0
    return max(0, int((datetime.now(timezone.utc) - started).total_seconds() * 1000))
