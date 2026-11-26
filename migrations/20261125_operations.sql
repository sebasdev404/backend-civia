CREATE TABLE IF NOT EXISTS audit_events (
 id VARCHAR(36) PRIMARY KEY, actor_id VARCHAR NOT NULL, actor_name VARCHAR NOT NULL,
 action VARCHAR(80) NOT NULL,target_id VARCHAR(160),details JSON NOT NULL,created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_events_action ON audit_events(action);
CREATE INDEX IF NOT EXISTS ix_audit_events_target_id ON audit_events(target_id);
CREATE INDEX IF NOT EXISTS ix_audit_events_created_at ON audit_events(created_at);
CREATE TABLE IF NOT EXISTS system_settings (key VARCHAR(80) PRIMARY KEY,value JSON NOT NULL,updated_by VARCHAR NOT NULL,updated_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS webhook_events (
 id VARCHAR(64) PRIMARY KEY,payload JSON NOT NULL,status VARCHAR(30) NOT NULL DEFAULT 'queued',attempts INTEGER NOT NULL DEFAULT 0,
 error TEXT,received_at TIMESTAMPTZ NOT NULL,processed_at TIMESTAMPTZ,last_attempt_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_webhook_events_status_received ON webhook_events(status,received_at);
