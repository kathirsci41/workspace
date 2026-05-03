import sys
sys.path.insert(0, '.')

# Test that the import works in a fresh process
from app.services.extraction.tasks import extract_document
from app.models import DocumentType

print("✓ DocumentType successfully imported")
print(f"✓ extract_document task: {extract_document}")
print(f"✓ DocumentType.CUSTOMER_PO = {DocumentType.CUSTOMER_PO}")
print("\nExtraction service is ready with correct imports!")

# Now let's manually queue a test extraction
from celery_app import celery_app
task_id = extract_document.delay("eafee27d-e014-41bd-a6e6-78aa3a401689")
print(f"\n✓ Queued extraction task: {task_id}")
