BEGIN;
CREATE TABLE IF NOT EXISTS case_workflow_events (
    id VARCHAR(36) PRIMARY KEY,
    case_id VARCHAR(50) NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
    event_type VARCHAR(40) NOT NULL,
    actor_id VARCHAR NOT NULL,
    actor_name VARCHAR NOT NULL,
    note TEXT NOT NULL,
    evidence_reference TEXT,
    before_state JSON NOT NULL,
    after_state JSON NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_case_workflow_events_case_created
ON case_workflow_events (case_id, created_at, id);
COMMIT;
