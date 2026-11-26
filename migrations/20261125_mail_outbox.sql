CREATE TABLE IF NOT EXISTS mail_outbox (
 id VARCHAR(36) PRIMARY KEY,recipient_key VARCHAR(64) NOT NULL,kind VARCHAR(30) NOT NULL,
 ciphertext TEXT NOT NULL,status VARCHAR(30) NOT NULL DEFAULT 'queued',attempts INTEGER NOT NULL DEFAULT 0,
 created_at TIMESTAMPTZ NOT NULL,next_attempt_at TIMESTAMPTZ NOT NULL,delivered_at TIMESTAMPTZ,error TEXT
);
CREATE INDEX IF NOT EXISTS ix_mail_outbox_recipient_key ON mail_outbox(recipient_key);
