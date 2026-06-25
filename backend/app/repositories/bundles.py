from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.order_bundle import OrderBundleRecord
from app.schemas.bundle import BundleCreate


class BundleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: BundleCreate) -> OrderBundleRecord:
        record = OrderBundleRecord(**payload.model_dump())
        self.db.add(record)
        self.db.flush()
        return record

    def list(self) -> list[OrderBundleRecord]:
        return list(self.db.scalars(select(OrderBundleRecord).order_by(OrderBundleRecord.created_at.desc())))

    def get(self, bundle_id: str) -> OrderBundleRecord | None:
        return self.db.get(OrderBundleRecord, bundle_id)

    def get_with_documents(self, bundle_id: str) -> OrderBundleRecord | None:
        stmt = select(OrderBundleRecord).where(OrderBundleRecord.id == bundle_id).options(selectinload(OrderBundleRecord.documents))
        return self.db.scalars(stmt).first()

    def delete(self, bundle: OrderBundleRecord) -> None:
        self.db.delete(bundle)

    def update_status(self, bundle: OrderBundleRecord, new_status: str) -> None:
        bundle.status = new_status
        bundle.updated_at = datetime.now(timezone.utc)

    def add_dismissed_check(self, bundle: OrderBundleRecord, check_id: str) -> list[str]:
        ids: list[str] = json.loads(bundle.dismissed_check_ids or "[]")
        if check_id not in ids:
            ids.append(check_id)
        bundle.dismissed_check_ids = json.dumps(ids)
        bundle.updated_at = datetime.now(timezone.utc)
        return ids

    def remove_dismissed_check(self, bundle: OrderBundleRecord, check_id: str) -> list[str]:
        ids: list[str] = json.loads(bundle.dismissed_check_ids or "[]")
        ids = [i for i in ids if i != check_id]
        bundle.dismissed_check_ids = json.dumps(ids)
        bundle.updated_at = datetime.now(timezone.utc)
        return ids
