CREATE TABLE IF NOT EXISTS case_comments (
    post_id VARCHAR(100) NOT NULL,
    comment_id VARCHAR(150) NOT NULL,
    case_id VARCHAR(50) NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    comment_json JSON NOT NULL,
    linked_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (post_id, comment_id)
);
CREATE INDEX IF NOT EXISTS ix_case_comments_case_id ON case_comments(case_id);
