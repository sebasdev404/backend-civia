BEGIN;
CREATE TABLE IF NOT EXISTS news_sources (
    source_id VARCHAR(80) PRIMARY KEY REFERENCES publication_sources(id),
    page_url VARCHAR(350) NOT NULL UNIQUE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS news_analyses (
    post_id VARCHAR(150) PRIMARY KEY REFERENCES observed_posts(id),
    fingerprint VARCHAR(64) NOT NULL,
    result_json TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMIT;
