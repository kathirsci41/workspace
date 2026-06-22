-- Sprint 1 Task 1.4: add celery_task_id to bundle_documents,
-- last_verified_at to order_bundles.

ALTER TABLE bundle_documents ADD COLUMN celery_task_id VARCHAR(36);
CREATE INDEX IF NOT EXISTS ix_bundle_documents_celery_task_id ON bundle_documents(celery_task_id);

ALTER TABLE order_bundles ADD COLUMN last_verified_at DATETIME;
