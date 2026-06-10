from __future__ import annotations

from collections.abc import Generator
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


_engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def configure_database(database_url: str) -> None:
    global _engine, SessionLocal
    _engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
    )
    SessionLocal.configure(bind=_engine)


def init_db(*, drop_existing: bool = False) -> None:
    from app.models.audit_event import AuditEventRecord
    from app.models.document import DocumentRecord
    from app.models.document_metadata import DocumentMetadataRecord
    from app.models.order_bundle import OrderBundleRecord
    from app.models.reference_index import ReferenceIndexRecord

    _ = (AuditEventRecord, DocumentRecord, DocumentMetadataRecord, OrderBundleRecord, ReferenceIndexRecord)
    if drop_existing:
        Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)


def wait_for_database(*, max_attempts: int | None = None, retry_seconds: float | None = None) -> None:
    attempts = max_attempts or settings.db_startup_max_attempts
    delay = retry_seconds if retry_seconds is not None else settings.db_startup_retry_seconds
    last_error: OperationalError | None = None
    for attempt in range(1, attempts + 1):
        try:
            with _engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except OperationalError as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(delay)
    raise RuntimeError(f"Database did not become ready after {attempts} attempts.") from last_error


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
