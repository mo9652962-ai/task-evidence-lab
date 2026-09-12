-- Append-only audit metadata for tamper evidence and verified archival.
ALTER TABLE audit_log ADD COLUMN actor_user_id INTEGER;
ALTER TABLE audit_log ADD COLUMN request_id TEXT;
ALTER TABLE audit_log ADD COLUMN previous_hash TEXT;
ALTER TABLE audit_log ADD COLUMN event_hash TEXT;
ALTER TABLE audit_log ADD COLUMN redaction_version TEXT NOT NULL DEFAULT 'v1';
ALTER TABLE audit_log ADD COLUMN archived_at TEXT;
ALTER TABLE audit_log ADD COLUMN archive_batch_id TEXT;
