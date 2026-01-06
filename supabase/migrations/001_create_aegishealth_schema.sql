-- AegisHealth Database Schema (Supabase Auth + RLS + Realtime)

-- =============================================================================
-- 1. Types
-- =============================================================================

CREATE TYPE user_role AS ENUM ('server', 'client');
CREATE TYPE job_status AS ENUM ('pending', 'running', 'completed', 'failed', 'stopped');
CREATE TYPE client_status AS ENUM ('active', 'inactive');
CREATE TYPE audit_event_type AS ENUM (
  'job_created', 'job_started', 'job_completed', 'job_failed', 'job_stopped',
  'round_started', 'round_completed',
  'client_registered', 'client_connected', 'client_update_received',
  'model_distributed', 'model_aggregated', 'model_released',
  'user_login', 'user_created'
);

-- =============================================================================
-- 2. Tables
-- =============================================================================

CREATE TABLE clients (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  region TEXT,
  status client_status DEFAULT 'active',
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  registered_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  role user_role NOT NULL DEFAULT 'server',
  client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
  full_name TEXT,
  email TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE training_jobs (
  id BIGSERIAL PRIMARY KEY,
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  status job_status DEFAULT 'pending',
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  total_rounds INTEGER NOT NULL DEFAULT 50,
  current_round INTEGER DEFAULT 0,
  best_accuracy DOUBLE PRECISION DEFAULT 0,
  best_f1_score DOUBLE PRECISION DEFAULT 0,
  best_auc_roc DOUBLE PRECISION DEFAULT 0,
  model_path_pt TEXT,
  model_path_onnx TEXT,
  model_released_at TIMESTAMPTZ DEFAULT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

CREATE TABLE training_rounds (
  id BIGSERIAL PRIMARY KEY,
  job_id BIGINT NOT NULL REFERENCES training_jobs(id) ON DELETE CASCADE,
  round_number INTEGER NOT NULL,
  global_loss DOUBLE PRECISION,
  global_accuracy DOUBLE PRECISION,
  global_f1_score DOUBLE PRECISION,
  global_auc_roc DOUBLE PRECISION,
  participating_clients INTEGER DEFAULT 0,
  aggregation_time_ms DOUBLE PRECISION,
  cumulative_epsilon DOUBLE PRECISION,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(job_id, round_number)
);

CREATE TABLE client_updates (
  id BIGSERIAL PRIMARY KEY,
  round_id BIGINT NOT NULL REFERENCES training_rounds(id) ON DELETE CASCADE,
  client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  local_loss DOUBLE PRECISION,
  local_accuracy DOUBLE PRECISION,
  samples_used INTEGER,
  dp_epsilon_spent DOUBLE PRECISION,
  cumulative_epsilon DOUBLE PRECISION,
  training_time_ms DOUBLE PRECISION,
  submitted_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE audit_logs (
  id BIGSERIAL PRIMARY KEY,
  event_type audit_event_type NOT NULL,
  actor_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  job_id BIGINT REFERENCES training_jobs(id) ON DELETE SET NULL,
  client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
  details JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE client_registry (
  client_id BIGINT PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
  num_samples INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'connected',
  last_heartbeat TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- 3. Functions
-- =============================================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
  _client_id BIGINT;
BEGIN
  _client_id := (NEW.raw_user_meta_data->>'client_id')::bigint;
  IF _client_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.clients WHERE id = _client_id) THEN
    _client_id := NULL;
  END IF;

  INSERT INTO public.profiles (id, role, client_id, full_name, email)
  VALUES (
    NEW.id,
    CASE
      WHEN NEW.raw_user_meta_data->>'role' IN ('server', 'client')
      THEN (NEW.raw_user_meta_data->>'role')::public.user_role
      ELSE 'server'::public.user_role
    END,
    _client_id,
    NEW.raw_user_meta_data->>'full_name',
    NEW.email
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION public.user_role()
RETURNS user_role AS $$
  SELECT role FROM public.profiles WHERE id = auth.uid()
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION public.user_client_id()
RETURNS BIGINT AS $$
  SELECT client_id FROM public.profiles WHERE id = auth.uid()
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- =============================================================================
-- 4. Triggers
-- =============================================================================

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- =============================================================================
-- 5. Indexes
-- =============================================================================

CREATE INDEX idx_training_rounds_job ON training_rounds(job_id);
CREATE INDEX idx_client_updates_round ON client_updates(round_id);
CREATE INDEX idx_client_updates_client ON client_updates(client_id);
CREATE INDEX idx_audit_logs_job ON audit_logs(job_id);
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);

-- =============================================================================
-- 6. RLS
-- =============================================================================

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_rounds ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_updates ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;

-- profiles
CREATE POLICY "profiles_select_own"
  ON profiles FOR SELECT
  USING (auth.uid() = id);

CREATE POLICY "profiles_update_own"
  ON profiles FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

CREATE POLICY "profiles_server_select_all"
  ON profiles FOR SELECT
  TO authenticated
  USING (user_role() = 'server');

-- clients
CREATE POLICY "clients_select_authenticated"
  ON clients FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "clients_server_insert"
  ON clients FOR INSERT
  TO authenticated
  WITH CHECK (user_role() = 'server');

-- training_jobs
CREATE POLICY "training_jobs_server_select"
  ON training_jobs FOR SELECT
  TO authenticated
  USING (user_role() = 'server');

CREATE POLICY "training_jobs_server_insert"
  ON training_jobs FOR INSERT
  TO authenticated
  WITH CHECK (user_role() = 'server' AND created_by = auth.uid());

CREATE POLICY "training_jobs_client_select"
  ON training_jobs FOR SELECT
  TO authenticated
  USING (user_role() = 'client');

-- training_rounds
CREATE POLICY "training_rounds_select"
  ON training_rounds FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM training_jobs tj
      WHERE tj.id = training_rounds.job_id
      AND (user_role() = 'server' OR user_role() = 'client')
    )
  );

-- client_updates
CREATE POLICY "client_updates_select"
  ON client_updates FOR SELECT
  TO authenticated
  USING (
    user_role() = 'server'
    OR (user_role() = 'client' AND client_id = user_client_id())
  );

-- audit_logs
CREATE POLICY "audit_logs_select"
  ON audit_logs FOR SELECT
  TO authenticated
  USING (
    user_role() = 'server'
    OR (user_role() = 'client' AND (client_id = user_client_id() OR client_id IS NULL))
  );

-- client_registry
CREATE POLICY "client_registry_select"
  ON client_registry FOR SELECT
  TO authenticated
  USING (
    user_role() = 'server'
    OR (user_role() = 'client' AND client_id = user_client_id())
  );

-- =============================================================================
-- 7. Realtime
-- =============================================================================

ALTER PUBLICATION supabase_realtime ADD TABLE training_jobs;
ALTER PUBLICATION supabase_realtime ADD TABLE training_rounds;
ALTER PUBLICATION supabase_realtime ADD TABLE client_registry;
ALTER PUBLICATION supabase_realtime ADD TABLE clients;
ALTER PUBLICATION supabase_realtime ADD TABLE audit_logs;

-- =============================================================================
-- 8. Grants
-- =============================================================================

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT SELECT, UPDATE ON public.profiles TO authenticated;
GRANT SELECT, INSERT ON public.clients TO authenticated;
GRANT SELECT, INSERT ON public.training_jobs TO authenticated;
GRANT SELECT ON public.training_rounds TO authenticated;
GRANT SELECT ON public.client_updates TO authenticated;
GRANT SELECT ON public.audit_logs TO authenticated;
GRANT SELECT ON public.client_registry TO authenticated;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- =============================================================================
-- 9. Storage (models bucket)
-- =============================================================================

INSERT INTO storage.buckets (id, name, public)
VALUES ('models', 'models', FALSE)
ON CONFLICT (id) DO NOTHING;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage' AND tablename = 'objects' AND policyname = 'models_read_authenticated'
  ) THEN
    CREATE POLICY models_read_authenticated
      ON storage.objects
      FOR SELECT
      TO authenticated
      USING (bucket_id = 'models');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage' AND tablename = 'objects' AND policyname = 'models_write_service_role'
  ) THEN
    CREATE POLICY models_write_service_role
      ON storage.objects
      FOR ALL
      TO service_role
      USING (bucket_id = 'models')
      WITH CHECK (bucket_id = 'models');
  END IF;
END $$;

