BEGIN;
CREATE TABLE IF NOT EXISTS password_recoveries (
    user_id VARCHAR PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    nonce VARCHAR(36) NOT NULL,
    code_digest VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    used_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS auth_rate_limits (
    key_hash VARCHAR(64) PRIMARY KEY,
    attempts INTEGER NOT NULL,
    reset_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_auth_rate_limits_reset_at ON auth_rate_limits (reset_at);
COMMIT;
