CREATE TABLE IF NOT EXISTS vendor_master (
  gstin VARCHAR(15) PRIMARY KEY,
  tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',
  vendor_name VARCHAR(256) NOT NULL,
  trade_name VARCHAR(256),
  state_code VARCHAR(2) NOT NULL,
  registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  is_active BOOLEAN NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS ix_vendor_master_tenant_id ON vendor_master(tenant_id);
