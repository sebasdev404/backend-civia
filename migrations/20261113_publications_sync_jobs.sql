-- main.py registra y crea estas tablas al arrancar. Alternativa para despliegues con migraciones explícitas.
CREATE TABLE IF NOT EXISTS publication_sources (
    id VARCHAR(80) PRIMARY KEY, name VARCHAR(160) NOT NULL, url TEXT NOT NULL,
    graph_node VARCHAR(160), status VARCHAR(40) NOT NULL DEFAULT 'not_checked', detail TEXT, checked_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS observed_posts (
    id VARCHAR(150) PRIMARY KEY, source_id VARCHAR(80) NOT NULL, title VARCHAR(255) NOT NULL,
    message TEXT, cover_image TEXT, media_type VARCHAR(40), permalink_url TEXT, created_time VARCHAR(80),
    total_comments INTEGER, raw_comments_json TEXT, updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_observed_posts_source_id ON observed_posts (source_id);
CREATE INDEX IF NOT EXISTS ix_observed_posts_created_time ON observed_posts (created_time);
CREATE TABLE IF NOT EXISTS publication_snapshots (
    post_id VARCHAR(150) PRIMARY KEY, likes_count INTEGER, reactions_count INTEGER, shares_count INTEGER,
    reactions_json TEXT, status VARCHAR(40) NOT NULL DEFAULT 'not_checked', detail TEXT, updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS meta_sync_jobs (
    id VARCHAR(36) PRIMARY KEY, active_key VARCHAR(200) UNIQUE, scope VARCHAR(200) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'queued', progress_json TEXT NOT NULL DEFAULT '{}', result_json TEXT,
    error TEXT, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_meta_sync_jobs_scope ON meta_sync_jobs (scope);
CREATE INDEX IF NOT EXISTS ix_meta_sync_jobs_created_at ON meta_sync_jobs (created_at);
