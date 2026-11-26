CREATE TABLE IF NOT EXISTS case_registrations (
    id VARCHAR(36) PRIMARY KEY,
    case_id VARCHAR(50) NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
    number VARCHAR(100) NOT NULL, institution VARCHAR(160) NOT NULL,
    issued_on DATE NOT NULL, evidence_reference TEXT NOT NULL, reason TEXT NOT NULL,
    actor_id VARCHAR NOT NULL, actor_name VARCHAR NOT NULL, created_at TIMESTAMPTZ NOT NULL,
    cancelled_at TIMESTAMPTZ, cancelled_by VARCHAR, cancellation_reason TEXT
);
CREATE INDEX IF NOT EXISTS ix_case_registrations_case_created ON case_registrations(case_id,created_at);
