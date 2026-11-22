-- Agro AI: Zero-Trust Admin Security & AgroGPT Telemetry Migration (Postgres / Supabase)
-- Review carefully before applying to staging or production.
-- Additive only: does not drop or alter existing farmer data.

BEGIN;

-- 1. AdminUser session revocation & MFA enforcement columns
ALTER TABLE admin_users
  ADD COLUMN IF NOT EXISTS mfa_enforced BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 1;

-- 2. AgroGPT telemetry (cost, routing, latency, guard flags; no raw prompts or PII)
CREATE TABLE IF NOT EXISTS agrogpt_usage_logs (
  id TEXT PRIMARY KEY,
  request_id VARCHAR(64) NOT NULL,
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  task_category VARCHAR(40),
  provider VARCHAR(40),
  model VARCHAR(80),
  source_tier VARCHAR(40) NOT NULL DEFAULT 'llm',
  guard_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
  latency_ms INTEGER,
  tokens_in INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0,
  estimated_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agrogpt_usage_request_id ON agrogpt_usage_logs(request_id);
CREATE INDEX IF NOT EXISTS idx_agrogpt_usage_user_created ON agrogpt_usage_logs(user_id, created_at DESC);

-- 3. AgroGPT farmer feedback
CREATE TABLE IF NOT EXISTS agrogpt_feedback (
  id TEXT PRIMARY KEY,
  message_id TEXT NOT NULL REFERENCES agro_gpt_messages(id) ON DELETE CASCADE,
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  rating VARCHAR(20) NOT NULL CHECK (rating IN ('helpful', 'not_helpful')),
  reason_tag VARCHAR(50),
  comment TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agrogpt_feedback_message ON agrogpt_feedback(message_id);

-- 4. Row Level Security (RLS) — Deny by default for anon / authenticated PostgREST clients.
--    Backend FastAPI service connects with privileged DB role; browser clients must never
--    read/write admin tables directly.
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_access_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE agrogpt_usage_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agrogpt_feedback ENABLE ROW LEVEL SECURITY;

-- Drop any overly permissive policies if they exist
DROP POLICY IF EXISTS admin_users_deny_all ON admin_users;
CREATE POLICY admin_users_deny_all ON admin_users
  FOR ALL TO anon, authenticated USING (FALSE) WITH CHECK (FALSE);

DROP POLICY IF EXISTS admin_audit_logs_deny_all ON admin_audit_logs;
CREATE POLICY admin_audit_logs_deny_all ON admin_audit_logs
  FOR ALL TO anon, authenticated USING (FALSE) WITH CHECK (FALSE);

DROP POLICY IF EXISTS admin_access_requests_deny_all ON admin_access_requests;
CREATE POLICY admin_access_requests_deny_all ON admin_access_requests
  FOR ALL TO anon, authenticated USING (FALSE) WITH CHECK (FALSE);

DROP POLICY IF EXISTS agrogpt_usage_logs_deny_all ON agrogpt_usage_logs;
CREATE POLICY agrogpt_usage_logs_deny_all ON agrogpt_usage_logs
  FOR ALL TO anon, authenticated USING (FALSE) WITH CHECK (FALSE);

-- Farmers may insert/read only their own feedback rows if accessed via Supabase client
DROP POLICY IF EXISTS agrogpt_feedback_own ON agrogpt_feedback;
CREATE POLICY agrogpt_feedback_own ON agrogpt_feedback
  FOR ALL TO authenticated
  USING (user_id = auth.uid()::text)
  WITH CHECK (user_id = auth.uid()::text);

-- 5. Tamper-resistance trigger on admin_audit_logs (blocks UPDATE and DELETE even for privileged SQL roles)
CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'admin_audit_logs is append-only; UPDATE and DELETE are forbidden';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_admin_audit_logs_immutable ON admin_audit_logs;
CREATE TRIGGER trg_admin_audit_logs_immutable
  BEFORE UPDATE OR DELETE ON admin_audit_logs
  FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation();

COMMIT;
