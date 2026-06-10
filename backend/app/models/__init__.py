"""All ORM model classes for the Order Assurance application.

Importing this package registers every model in Base.metadata so that
Base.metadata.create_all() and init_db() create all tables without
callers having to import individual model modules.
"""
from app.models.audit_event import AuditEventRecord
from app.models.document import DocumentRecord
from app.models.document_metadata import DocumentMetadataRecord
from app.models.order_bundle import OrderBundleRecord
from app.models.reference_index import ReferenceIndexRecord
from app.models.document_page import DocumentPageRecord
from app.models.text_source import TextSourceRecord
from app.models.field_candidate import FieldCandidateRecord

__all__ = [
    "AuditEventRecord",
    "DocumentRecord",
    "DocumentMetadataRecord",
    "OrderBundleRecord",
    "ReferenceIndexRecord",
    "DocumentPageRecord",
    "TextSourceRecord",
    "FieldCandidateRecord",
]
