#!/usr/bin/env python3
"""
Re-extract all documents in the application.
Triggers the extraction pipeline for every document.
"""
import asyncio
import sys
import os

# Add parent directory to path so 'app' module can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.document import Document
from app.services.extraction.tasks import extract_document
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reextract_all():
    """Re-extract all documents."""
    # Create async engine
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Get all documents
        result = await db.execute(select(Document))
        documents = result.scalars().all()

        total = len(documents)
        logger.info(f"Found {total} documents to re-extract")

        if total == 0:
            logger.info("No documents to re-extract")
            await engine.dispose()
            return

        # Re-extract each document
        for i, doc in enumerate(documents, 1):
            logger.info(f"[{i}/{total}] Re-extracting document {doc.id} ({doc.document_type})")
            try:
                # Trigger extraction task
                await extract_document.apply_async(
                    args=(str(doc.id),),
                    task_id=f"reextract_{doc.id}"
                ).get(timeout=600)  # 10 min timeout per document
                logger.info(f"✓ Document {doc.id} extraction triggered")
            except Exception as e:
                logger.error(f"✗ Failed to re-extract {doc.id}: {str(e)}")

        logger.info(f"Re-extraction complete! Processed {total} documents")

    await engine.dispose()

if __name__ == "__main__":
    try:
        asyncio.run(reextract_all())
    except KeyboardInterrupt:
        logger.info("Re-extraction cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Re-extraction failed: {str(e)}")
        sys.exit(1)
