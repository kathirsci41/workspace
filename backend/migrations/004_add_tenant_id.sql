-- Sprint 1 Task 1.5: add tenant_id (default='default') to 5 tables.

ALTER TABLE order_bundles ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT 'default';
CREATE INDEX IF NOT EXISTS ix_order_bundles_tenant_id ON order_bundles(tenant_id);

ALTER TABLE bundle_documents ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT 'default';
CREATE INDEX IF NOT EXISTS ix_bundle_documents_tenant_id ON bundle_documents(tenant_id);

ALTER TABLE document_metadata ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT 'default';
CREATE INDEX IF NOT EXISTS ix_document_metadata_tenant_id ON document_metadata(tenant_id);

ALTER TABLE audit_events ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT 'default';
CREATE INDEX IF NOT EXISTS ix_audit_events_tenant_id ON audit_events(tenant_id);

ALTER TABLE reference_index ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT 'default';
CREATE INDEX IF NOT EXISTS ix_reference_index_tenant_id ON reference_index(tenant_id);
