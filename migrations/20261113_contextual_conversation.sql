-- main.py crea estas tablas automáticamente al iniciar. Alternativa para despliegues con migración explícita.
CREATE TABLE IF NOT EXISTS post_contexts (
    post_id VARCHAR(100) PRIMARY KEY,
    summary TEXT NOT NULL DEFAULT '',
    transcript TEXT NOT NULL DEFAULT '',
    updated_by VARCHAR(100),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS comment_analyses (
    post_id VARCHAR(100) NOT NULL,
    comment_id VARCHAR(150) NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    result_json TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (post_id, comment_id)
);
