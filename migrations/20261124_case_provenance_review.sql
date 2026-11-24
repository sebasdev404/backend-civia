CREATE TABLE IF NOT EXISTS case_provenance_reviews (
    case_id VARCHAR(50) PRIMARY KEY REFERENCES cases(id) ON DELETE CASCADE,
    batch VARCHAR(80) NOT NULL,
    status VARCHAR(40) NOT NULL,
    reason VARCHAR(80) NOT NULL,
    evidence_json JSON NOT NULL,
    reviewed_by VARCHAR(100) NOT NULL,
    checked_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_case_provenance_reviews_batch ON case_provenance_reviews(batch);
