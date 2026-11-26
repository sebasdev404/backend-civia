BEGIN;
CREATE TABLE IF NOT EXISTS case_corrections (
    id VARCHAR(36) PRIMARY KEY,
    case_id VARCHAR(50) NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
    disposition VARCHAR(40) NOT NULL,
    reason TEXT NOT NULL,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    evidence_json JSON NOT NULL,
    undone_at TIMESTAMPTZ,
    undone_by VARCHAR(100),
    undo_reason TEXT
);
CREATE INDEX IF NOT EXISTS ix_case_corrections_case_id ON case_corrections(case_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_case_correction ON case_corrections(case_id) WHERE undone_at IS NULL;
COMMIT;
