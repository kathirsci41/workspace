CREATE TABLE IF NOT EXISTS order_bundles (
  id VARCHAR(36) PRIMARY KEY,
  bundle_number VARCHAR(100) UNIQUE NOT NULL,
  customer_name VARCHAR(255),
  customer_po_no VARCHAR(100),
  so_no VARCHAR(100),
  status VARCHAR(50) NOT NULL DEFAULT 'REVIEW_REQUIRED',
  customer_delivery_status VARCHAR(50) NOT NULL DEFAULT 'REVIEW_REQUIRED',
  vendor_procurement_status VARCHAR(50) NOT NULL DEFAULT 'REVIEW_REQUIRED',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS bundle_documents (
  id VARCHAR(36) PRIMARY KEY,
  order_bundle_id VARCHAR(36) NOT NULL REFERENCES order_bundles(id),
  document_type VARCHAR(50) NOT NULL,
  filename VARCHAR(255) NOT NULL,
  content_type VARCHAR(100),
  storage_path VARCHAR(500),
  status VARCHAR(50) NOT NULL DEFAULT 'UPLOADED',
  last_error VARCHAR(500),
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS document_metadata (
  id VARCHAR(36) PRIMARY KEY,
  document_id VARCHAR(36) NOT NULL UNIQUE REFERENCES bundle_documents(id),
  status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
  extracted_data JSON NOT NULL,
  diagnostics JSON NOT NULL,
  primary_ref_no VARCHAR(150),
  po_ref_no VARCHAR(150),
  last_error VARCHAR(500),
  updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS reference_index (
  id VARCHAR(36) PRIMARY KEY,
  document_id VARCHAR(36) NOT NULL REFERENCES bundle_documents(id),
  order_bundle_id VARCHAR(36) REFERENCES order_bundles(id),
  reference_type VARCHAR(80) NOT NULL,
  reference_value VARCHAR(255) NOT NULL,
  source_type VARCHAR(50),
  document_type VARCHAR(50),
  field_name VARCHAR(80),
  confidence FLOAT,
  evidence_text VARCHAR(500),
  created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
  id VARCHAR(36) PRIMARY KEY,
  event_type VARCHAR(100) NOT NULL,
  actor VARCHAR(100) NOT NULL DEFAULT 'system',
  document_id VARCHAR(36),
  order_bundle_id VARCHAR(36),
  payload JSON NOT NULL,
  created_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_order_bundles_bundle_number ON order_bundles(bundle_number);
CREATE INDEX IF NOT EXISTS ix_bundle_documents_order_bundle_id ON bundle_documents(order_bundle_id);
CREATE INDEX IF NOT EXISTS ix_bundle_documents_document_type ON bundle_documents(document_type);
CREATE INDEX IF NOT EXISTS ix_document_metadata_document_id ON document_metadata(document_id);
CREATE INDEX IF NOT EXISTS ix_reference_index_document_id ON reference_index(document_id);
CREATE INDEX IF NOT EXISTS ix_reference_index_order_bundle_id ON reference_index(order_bundle_id);
CREATE INDEX IF NOT EXISTS ix_reference_index_reference_type ON reference_index(reference_type);
CREATE INDEX IF NOT EXISTS ix_reference_index_reference_value ON reference_index(reference_value);
CREATE INDEX IF NOT EXISTS ix_audit_events_event_type ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS ix_audit_events_document_id ON audit_events(document_id);
CREATE INDEX IF NOT EXISTS ix_audit_events_order_bundle_id ON audit_events(order_bundle_id);
