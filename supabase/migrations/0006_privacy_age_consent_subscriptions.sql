-- Agro AI Privacy-First Age Verification, Parental Consent & Cookie Consent Migration
-- Enables Row Level Security (RLS) and least-privilege policies on Supabase.

ALTER TABLE IF EXISTS public.users
  ADD COLUMN IF NOT EXISTS date_of_birth VARCHAR(10),
  ADD COLUMN IF NOT EXISTS country_code VARCHAR(2) DEFAULT 'IN',
  ADD COLUMN IF NOT EXISTS age_category VARCHAR(20),
  ADD COLUMN IF NOT EXISTS account_status VARCHAR(32) DEFAULT 'active',
  ADD COLUMN IF NOT EXISTS consent_version VARCHAR(20),
  ADD COLUMN IF NOT EXISTS consent_timestamp TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS public.parental_consents (
  id TEXT PRIMARY KEY,
  child_user_id TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  parent_contact VARCHAR(255) NOT NULL,
  parent_user_id TEXT,
  consent_version VARCHAR(20) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  verification_method VARCHAR(40) NOT NULL DEFAULT 'parent_otp_challenge',
  verification_code_hash VARCHAR(128) NOT NULL,
  purpose_summary TEXT NOT NULL,
  requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  responded_at TIMESTAMPTZ,
  withdrawn_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_parental_consents_child ON public.parental_consents(child_user_id);

CREATE TABLE IF NOT EXISTS public.privacy_consent_records (
  id TEXT PRIMARY KEY,
  user_id TEXT REFERENCES public.users(id) ON DELETE CASCADE,
  subject_key VARCHAR(128) NOT NULL,
  essential BOOLEAN NOT NULL DEFAULT TRUE,
  analytics BOOLEAN NOT NULL DEFAULT FALSE,
  marketing BOOLEAN NOT NULL DEFAULT FALSE,
  consent_version VARCHAR(20) NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_privacy_consent_user ON public.privacy_consent_records(user_id);

CREATE TABLE IF NOT EXISTS public.privacy_audit_logs (
  id TEXT PRIMARY KEY,
  actor_user_id TEXT,
  target_user_id TEXT,
  event_type VARCHAR(64) NOT NULL,
  details JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable Row Level Security (RLS) on all privacy, consent, and subscription tables
ALTER TABLE public.parental_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.privacy_consent_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.privacy_audit_logs ENABLE ROW LEVEL SECURITY;

-- Least-privilege RLS policies (service_role bypasses RLS server-side; clients only access own rows)
DROP POLICY IF EXISTS parental_consents_child_select ON public.parental_consents;
CREATE POLICY parental_consents_child_select ON public.parental_consents
  FOR SELECT USING (auth.uid()::text = child_user_id OR auth.uid()::text = parent_user_id);

DROP POLICY IF EXISTS privacy_consent_owner_all ON public.privacy_consent_records;
CREATE POLICY privacy_consent_owner_all ON public.privacy_consent_records
  FOR ALL USING (auth.uid()::text = user_id)
  WITH CHECK (auth.uid()::text = user_id);

-- Audit logs are append-only via backend service role; no direct client read/write
DROP POLICY IF EXISTS privacy_audit_no_client_access ON public.privacy_audit_logs;
CREATE POLICY privacy_audit_no_client_access ON public.privacy_audit_logs
  FOR SELECT USING (FALSE);
