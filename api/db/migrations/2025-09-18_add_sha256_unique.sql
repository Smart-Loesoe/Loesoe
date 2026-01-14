CREATE TABLE IF NOT EXISTS uploads (
  id UUID PRIMARY KEY,
  session_id TEXT NOT NULL,
  filename TEXT NOT NULL,
  sha256 TEXT,
  stored_path TEXT,
  first_seen_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE uploads
  ADD COLUMN IF NOT EXISTS sha256 TEXT,
  ADD COLUMN IF NOT EXISTS stored_path TEXT,
  ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ DEFAULT now();

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE indexname = 'uq_uploads_session_sha256'
  ) THEN
    CREATE UNIQUE INDEX uq_uploads_session_sha256
      ON uploads(session_id, sha256);
  END IF;
END$$;
