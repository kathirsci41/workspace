#!/usr/bin/env python3
"""Test extraction with fresh Celery worker."""
import asyncio
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.models import Document, DocumentMetadata, DocumentStatus, MetadataStatus


async def reset_and_test():
    """Reset a failed document and trigger re-extraction."""
    # Create async engine
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        # Reset one failed document
        doc_id = UUID("eafee27d-e014-41bd-a6e6-78aa3a401689")

        # Update document status
        await conn.execute(
            __import__('sqlalchemy').update(Document)
            .where(Document.id == doc_id)
            .values(status=DocumentStatus.UPLOADED)
        )

        # Update metadata status
        await conn.execute(
            __import__('sqlalchemy').update(DocumentMetadata)
            .where(DocumentMetadata.document_id == doc_id)
            .values(status=MetadataStatus.PENDING, last_error=None)
        )

        await conn.commit()
        print(f"✓ Reset document {doc_id}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reset_and_test())
