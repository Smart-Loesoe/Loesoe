-- Voeg mime_type toe als die nog niet bestaat
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'uploads' AND column_name = 'mime_type'
  ) THEN
    ALTER TABLE uploads ADD COLUMN mime_type TEXT NOT NULL DEFAULT 'application/octet-stream';
  END IF;
END$$;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'uploads' AND column_name = 'mime_type'
  ) THEN
    ALTER TABLE uploads ADD COLUMN mime_type TEXT NOT NULL DEFAULT 'application/octet-stream';
  END IF;
END$$;
