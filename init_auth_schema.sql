-- Basis users-tabel voor auth
-- (simpel & robuust; geen extensions nodig)

CREATE TABLE IF NOT EXISTS users (
  id            BIGSERIAL PRIMARY KEY,
  email         VARCHAR(320) NOT NULL,
  password_hash TEXT         NOT NULL,
  name          VARCHAR(200),
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Unieke constraint op email (case-insensitive via lower())
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes 
    WHERE schemaname = 'public' AND indexname = 'ux_users_email_lower'
  ) THEN
    CREATE UNIQUE INDEX ux_users_email_lower ON users (LOWER(email));
  END IF;
END $$;
