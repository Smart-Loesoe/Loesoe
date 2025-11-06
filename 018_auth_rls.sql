-- Extensies
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

-- Users-tabel
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email CITEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  share_aggregated BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Helpers voor conditionele ALTER/CREATE op bestaande tabellen
DO $$
BEGIN
  -- MEMORY
  IF to_regclass('public.memory') IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='memory' AND column_name='user_id'
    ) THEN
      EXECUTE 'ALTER TABLE public.memory ADD COLUMN user_id uuid';
    END IF;

    EXECUTE 'ALTER TABLE public.memory ENABLE ROW LEVEL SECURITY';

    IF NOT EXISTS (
      SELECT 1 FROM pg_policies
      WHERE schemaname='public' AND tablename='memory' AND policyname='memory_user_isolation'
    ) THEN
      EXECUTE 'CREATE POLICY memory_user_isolation ON public.memory ' ||
              'USING (user_id = nullif(current_setting(''app.current_user'', true), '''')::uuid) ' ||
              'WITH CHECK (user_id = nullif(current_setting(''app.current_user'', true), '''')::uuid)';
    END IF;
  END IF;

  -- UPLOADS
  IF to_regclass('public.uploads') IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='uploads' AND column_name='user_id'
    ) THEN
      EXECUTE 'ALTER TABLE public.uploads ADD COLUMN user_id uuid';
    END IF;

    EXECUTE 'ALTER TABLE public.uploads ENABLE ROW LEVEL SECURITY';

    IF NOT EXISTS (
      SELECT 1 FROM pg_policies
      WHERE schemaname='public' AND tablename='uploads' AND policyname='uploads_user_isolation'
    ) THEN
      EXECUTE 'CREATE POLICY uploads_user_isolation ON public.uploads ' ||
              'USING (user_id = nullif(current_setting(''app.current_user'', true), '''')::uuid) ' ||
              'WITH CHECK (user_id = nullif(current_setting(''app.current_user'', true), '''')::uuid)';
    END IF;
  END IF;

  -- HISTORY
  IF to_regclass('public.history') IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='history' AND column_name='user_id'
    ) THEN
      EXECUTE 'ALTER TABLE public.history ADD COLUMN user_id uuid';
    END IF;

    EXECUTE 'ALTER TABLE public.history ENABLE ROW LEVEL SECURITY';

    IF NOT EXISTS (
      SELECT 1 FROM pg_policies
      WHERE schemaname='public' AND tablename='history' AND policyname='history_user_isolation'
    ) THEN
      EXECUTE 'CREATE POLICY history_user_isolation ON public.history ' ||
              'USING (user_id = nullif(current_setting(''app.current_user'', true), '''')::uuid) ' ||
              'WITH CHECK (user_id = nullif(current_setting(''app.current_user'', true), '''')::uuid)';
    END IF;
  END IF;
END
$$;
