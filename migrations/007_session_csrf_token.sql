-- Bind browser write requests to the opaque application session.
ALTER TABLE user_sessions ADD COLUMN csrf_token_hash TEXT;
