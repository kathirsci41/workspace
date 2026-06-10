-- Phase 1b: Evidence-layer tables.
--
-- These tables store page-level evidence, cached OCR/text-source output, and
-- field candidates ahead of resolver selection.  They are append-only
-- infrastructure that the extraction pipeline will write to in later phases;
-- no existing extraction, parser, verification, or export logic is changed by
-- this migration.
--
-- All types are SQLite-compatible (TEXT, INTEGER, REAL, BOOLEAN).

-- ---------------------------------------------------------------------------
-- document_pages
-- One row per page of each uploaded document.
-- Stores the image path/hash used for OCR, rotation, and page classification.
-- UNIQUE(document_id, page_number) prevents duplicate page records.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_pages (
    id                  TEXT PRIMARY KEY,
    document_id         TEXT NOT NULL,
    page_number         INTEGER NOT NULL,
    image_path          TEXT,
    image_hash          TEXT,
    has_digital_text    BOOLEAN,
    rotation_detected   INTEGER,
    page_classification TEXT,
    created_at          TEXT NOT NULL,
    UNIQUE (document_id, page_number)
);

CREATE INDEX IF NOT EXISTS ix_document_pages_document_id
    ON document_pages (document_id);

-- ---------------------------------------------------------------------------
-- text_sources
-- Cached OCR / digital-text output per page per provider.
-- UNIQUE(document_id, page_number, provider, settings_hash, image_hash)
-- prevents re-inserting the same OCR run.  NULL values in the unique columns
-- are treated as distinct by SQLite (each NULL != NULL), which is correct
-- behaviour for optional hash fields.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS text_sources (
    id                TEXT PRIMARY KEY,
    document_id       TEXT NOT NULL,
    page_number       INTEGER NOT NULL,
    source_type       TEXT NOT NULL,   -- digital_pdf | glm_ocr | pp_ocr_v5 | ...
    provider          TEXT NOT NULL,
    provider_version  TEXT,
    settings_hash     TEXT,
    settings_json     TEXT,
    raw_text          TEXT,
    normalized_text   TEXT,
    success           BOOLEAN NOT NULL,
    error             TEXT,
    duration_ms       INTEGER,
    image_hash        TEXT,
    created_at        TEXT NOT NULL,
    UNIQUE (document_id, page_number, provider, settings_hash, image_hash)
);

CREATE INDEX IF NOT EXISTS ix_text_sources_document_id
    ON text_sources (document_id);

CREATE INDEX IF NOT EXISTS ix_text_sources_provider
    ON text_sources (provider);

-- ---------------------------------------------------------------------------
-- field_candidates
-- All candidate values produced by the parser before resolver selection.
-- selection_status values: candidate | selected | rejected | manual_override
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS field_candidates (
    id               TEXT PRIMARY KEY,
    document_id      TEXT NOT NULL,
    field_key        TEXT NOT NULL,
    candidate_value  TEXT,
    normalized_value TEXT,
    source_type      TEXT NOT NULL,
    provider         TEXT,
    text_source_id   TEXT,
    page_number      INTEGER,
    evidence_text    TEXT,
    confidence       REAL,
    selection_status TEXT NOT NULL,
    rejection_reason TEXT,
    created_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_field_candidates_document_id
    ON field_candidates (document_id);

CREATE INDEX IF NOT EXISTS ix_field_candidates_field_key
    ON field_candidates (field_key);

CREATE INDEX IF NOT EXISTS ix_field_candidates_selection_status
    ON field_candidates (selection_status);
