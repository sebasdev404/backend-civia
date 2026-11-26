-- Reversible case relationships; no case data or comment ownership is rewritten.
BEGIN;
CREATE TABLE IF NOT EXISTS case_consolidations (
    id VARCHAR(36) PRIMARY KEY,
    primary_case_id VARCHAR(50) NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
    duplicate_case_id VARCHAR(50) NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    evidence_json JSON NOT NULL,
    undone_at TIMESTAMPTZ,
    undone_by VARCHAR(100),
    undo_reason TEXT,
    CONSTRAINT ck_consolidation_distinct_cases CHECK (primary_case_id <> duplicate_case_id)
);
CREATE INDEX IF NOT EXISTS ix_case_consolidations_primary_case_id ON case_consolidations(primary_case_id);
CREATE INDEX IF NOT EXISTS ix_case_consolidations_duplicate_case_id ON case_consolidations(duplicate_case_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_case_duplicate ON case_consolidations(duplicate_case_id) WHERE undone_at IS NULL;
COMMIT;
