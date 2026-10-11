-- ═══════════════════════════════════════════════════════════════════════════
-- AGRO AI — MIGRATION 0003: ADMIN ROLES, SUBSCRIPTION PLANS, ENTITLEMENTS & PAYMENTS
-- RLS Enforced on all tables. Idempotent webhook tracking. Immutable audit logs.
-- ═══════════════════════════════════════════════════════════════════════════

-- 1. ADMIN USERS TABLE
CREATE TABLE IF NOT EXISTS public.admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('super_admin', 'plan_manager', 'payment_manager', 'support_agent', 'content_manager', 'analyst')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for fast user auth checks
CREATE INDEX IF NOT EXISTS idx_admin_users_user_id ON public.admin_users(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON public.admin_users(role);

-- 2. SECURITY DEFINER HELPER FOR RLS
CREATE OR REPLACE FUNCTION public.is_admin(role_list TEXT[] DEFAULT NULL)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
STABLE
AS $$
DECLARE
    caller_role TEXT;
    caller_active BOOLEAN;
BEGIN
    IF auth.uid() IS NULL THEN
        RETURN false;
    END IF;

    SELECT role, is_active INTO caller_role, caller_active
    FROM public.admin_users
    WHERE user_id = auth.uid();

    IF caller_role IS NULL OR caller_active IS NOT TRUE THEN
        RETURN false;
    END IF;

    -- Super admin has universal access
    IF caller_role = 'super_admin' THEN
        RETURN true;
    END IF;

    -- If specific roles requested, check membership
    IF role_list IS NOT NULL THEN
        RETURN caller_role = ANY(role_list);
    END IF;

    RETURN true;
END;
$$;

-- 3. SUBSCRIPTION PLANS TABLE
CREATE TABLE IF NOT EXISTS public.subscription_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'paused', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subscription_plans_status ON public.subscription_plans(status);

-- 4. SUBSCRIPTION PLAN VERSIONS (Immutable Once Published)
CREATE TABLE IF NOT EXISTS public.subscription_plan_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES public.subscription_plans(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    name TEXT NOT NULL,
    description TEXT,
    price_minor INTEGER NOT NULL CHECK (price_minor >= 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    billing_interval TEXT NOT NULL CHECK (billing_interval IN ('monthly', 'quarterly', 'yearly', 'lifetime')),
    trial_days INTEGER NOT NULL DEFAULT 0 CHECK (trial_days >= 0),
    benefits JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_published BOOLEAN NOT NULL DEFAULT false,
    available_from TIMESTAMPTZ,
    available_until TIMESTAMPTZ,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(plan_id, version)
);

CREATE INDEX IF NOT EXISTS idx_plan_versions_plan_id ON public.subscription_plan_versions(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_versions_published ON public.subscription_plan_versions(is_published);

-- Immutability enforcement trigger on published plan versions
CREATE OR REPLACE FUNCTION public.check_plan_version_immutability()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- If already published, prevent modifications to core pricing and terms
    IF OLD.is_published = true THEN
        IF NEW.price_minor <> OLD.price_minor OR
           NEW.currency <> OLD.currency OR
           NEW.billing_interval <> OLD.billing_interval OR
           NEW.name <> OLD.name OR
           NEW.version <> OLD.version OR
           NEW.plan_id <> OLD.plan_id THEN
            RAISE EXCEPTION 'Published plan versions are immutable. Create a new version instead.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_plan_version_immutable ON public.subscription_plan_versions;
CREATE TRIGGER trg_plan_version_immutable
BEFORE UPDATE ON public.subscription_plan_versions
FOR EACH ROW
EXECUTE FUNCTION public.check_plan_version_immutability();

-- 5. PLAN ENTITLEMENTS (Feature Gating)
CREATE TABLE IF NOT EXISTS public.plan_entitlements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_version_id UUID NOT NULL REFERENCES public.subscription_plan_versions(id) ON DELETE CASCADE,
    feature_key TEXT NOT NULL CHECK (feature_key IN ('kisan_chat', 'diagnose_leaf', 'mandi_price', 'satellite_ndvi', 'soil_dna', 'logistics_trips', 'drone_spray')),
    enabled BOOLEAN NOT NULL DEFAULT true,
    usage_limit INTEGER CHECK (usage_limit IS NULL OR usage_limit >= 0), -- NULL = unlimited
    limit_period TEXT CHECK (limit_period IN ('daily', 'monthly', 'total')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(plan_version_id, feature_key)
);

CREATE INDEX IF NOT EXISTS idx_entitlements_version_feature ON public.plan_entitlements(plan_version_id, feature_key);

-- 6. USER SUBSCRIPTIONS
CREATE TABLE IF NOT EXISTS public.user_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan_version_id UUID NOT NULL REFERENCES public.subscription_plan_versions(id),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('trialing', 'active', 'past_due', 'canceled', 'expired')),
    current_period_start TIMESTAMPTZ NOT NULL DEFAULT now(),
    current_period_end TIMESTAMPTZ NOT NULL,
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON public.user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status ON public.user_subscriptions(status);

-- 7. SUBSCRIPTION USAGE
CREATE TABLE IF NOT EXISTS public.subscription_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    feature_key TEXT NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    used INTEGER NOT NULL DEFAULT 0 CHECK (used >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, feature_key, period_start)
);

CREATE INDEX IF NOT EXISTS idx_usage_user_feature ON public.subscription_usage(user_id, feature_key, period_start);

-- 8. PAYMENT ORDERS
CREATE TABLE IF NOT EXISTS public.payment_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan_version_id UUID NOT NULL REFERENCES public.subscription_plan_versions(id),
    amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    status TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'attempted', 'paid', 'failed', 'refunded')),
    provider TEXT NOT NULL DEFAULT 'razorpay',
    provider_order_id TEXT UNIQUE,
    receipt TEXT,
    notes JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payment_orders_user_id ON public.payment_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_orders_status ON public.payment_orders(status);

-- 9. PAYMENT TRANSACTIONS
CREATE TABLE IF NOT EXISTS public.payment_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES public.payment_orders(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'refunded', 'pending')),
    provider TEXT NOT NULL DEFAULT 'razorpay',
    provider_payment_id TEXT UNIQUE,
    provider_signature TEXT,
    error_code TEXT,
    error_description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_transactions_order_id ON public.payment_transactions(order_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON public.payment_transactions(user_id);

-- 10. PAYMENT WEBHOOK EVENTS (Idempotent by provider event id)
CREATE TABLE IF NOT EXISTS public.payment_webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL DEFAULT 'razorpay',
    provider_event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    processed BOOLEAN NOT NULL DEFAULT false,
    processed_at TIMESTAMPTZ,
    error_log TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(provider, provider_event_id)
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_lookup ON public.payment_webhook_events(provider, provider_event_id);

-- 11. ADMIN AUDIT LOGS (Service-Role Insert Only; No Update/Delete)
CREATE TABLE IF NOT EXISTS public.admin_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID REFERENCES auth.users(id),
    actor_role TEXT NOT NULL,
    action TEXT NOT NULL,
    target_entity TEXT NOT NULL,
    target_id TEXT,
    details JSONB DEFAULT '{}'::jsonb,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_actor ON public.admin_audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_action ON public.admin_audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_admin_audit_entity ON public.admin_audit_logs(target_entity, target_id);

-- Revoke all modifications on audit log table to guarantee tamper-evidence
REVOKE UPDATE, DELETE, TRUNCATE ON public.admin_audit_logs FROM PUBLIC, authenticated, anon;

-- ═══════════════════════════════════════════════════════════════════════════
-- 12. ROW LEVEL SECURITY (RLS) POLICIES
-- ═══════════════════════════════════════════════════════════════════════════

ALTER TABLE public.admin_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscription_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscription_plan_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plan_entitlements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscription_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payment_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payment_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payment_webhook_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admin_audit_logs ENABLE ROW LEVEL SECURITY;

-- ── ADMIN USERS RLS ──
CREATE POLICY admin_users_read_self ON public.admin_users
    FOR SELECT TO authenticated
    USING (user_id = auth.uid() OR public.is_admin(ARRAY['super_admin']));

CREATE POLICY admin_users_super_admin_manage ON public.admin_users
    FOR ALL TO authenticated
    USING (public.is_admin(ARRAY['super_admin']))
    WITH CHECK (public.is_admin(ARRAY['super_admin']));

-- ── SUBSCRIPTION PLANS RLS ──
CREATE POLICY plans_farmer_read_published ON public.subscription_plans
    FOR SELECT TO authenticated, anon
    USING (status = 'published' OR public.is_admin(ARRAY['super_admin', 'plan_manager', 'analyst']));

CREATE POLICY plans_admin_manage ON public.subscription_plans
    FOR ALL TO authenticated
    USING (public.is_admin(ARRAY['super_admin', 'plan_manager']))
    WITH CHECK (public.is_admin(ARRAY['super_admin', 'plan_manager']));

-- ── PLAN VERSIONS RLS ──
CREATE POLICY plan_versions_farmer_read ON public.subscription_plan_versions
    FOR SELECT TO authenticated, anon
    USING (is_published = true OR public.is_admin(ARRAY['super_admin', 'plan_manager', 'analyst']));

CREATE POLICY plan_versions_admin_manage ON public.subscription_plan_versions
    FOR ALL TO authenticated
    USING (public.is_admin(ARRAY['super_admin', 'plan_manager']))
    WITH CHECK (public.is_admin(ARRAY['super_admin', 'plan_manager']));

-- ── PLAN ENTITLEMENTS RLS ──
CREATE POLICY entitlements_read ON public.plan_entitlements
    FOR SELECT TO authenticated, anon
    USING (
        EXISTS (
            SELECT 1 FROM public.subscription_plan_versions v
            WHERE v.id = plan_entitlements.plan_version_id
            AND (v.is_published = true OR public.is_admin(ARRAY['super_admin', 'plan_manager', 'analyst']))
        )
    );

CREATE POLICY entitlements_admin_manage ON public.plan_entitlements
    FOR ALL TO authenticated
    USING (public.is_admin(ARRAY['super_admin', 'plan_manager']))
    WITH CHECK (public.is_admin(ARRAY['super_admin', 'plan_manager']));

-- ── USER SUBSCRIPTIONS RLS ──
CREATE POLICY subscriptions_farmer_read_own ON public.user_subscriptions
    FOR SELECT TO authenticated
    USING (user_id = auth.uid() OR public.is_admin(ARRAY['super_admin', 'plan_manager', 'payment_manager', 'support_agent', 'analyst']));

-- Regular users can NEVER write or edit subscriptions (Only Edge Functions / Service-Role)
CREATE POLICY subscriptions_admin_manage ON public.user_subscriptions
    FOR ALL TO authenticated
    USING (public.is_admin(ARRAY['super_admin', 'plan_manager', 'support_agent']))
    WITH CHECK (public.is_admin(ARRAY['super_admin', 'plan_manager', 'support_agent']));

-- ── SUBSCRIPTION USAGE RLS ──
CREATE POLICY usage_farmer_read_own ON public.subscription_usage
    FOR SELECT TO authenticated
    USING (user_id = auth.uid() OR public.is_admin(ARRAY['super_admin', 'support_agent', 'analyst']));

-- ── PAYMENT ORDERS RLS ──
CREATE POLICY orders_farmer_read_own ON public.payment_orders
    FOR SELECT TO authenticated
    USING (user_id = auth.uid() OR public.is_admin(ARRAY['super_admin', 'payment_manager', 'support_agent', 'analyst']));

-- ── PAYMENT TRANSACTIONS RLS ──
CREATE POLICY transactions_farmer_read_own ON public.payment_transactions
    FOR SELECT TO authenticated
    USING (user_id = auth.uid() OR public.is_admin(ARRAY['super_admin', 'payment_manager', 'support_agent', 'analyst']));

-- ── PAYMENT WEBHOOK EVENTS RLS ──
-- Strictly closed to clients. Only readable by admins with payment access.
CREATE POLICY webhooks_admin_read ON public.payment_webhook_events
    FOR SELECT TO authenticated
    USING (public.is_admin(ARRAY['super_admin', 'payment_manager']));

-- ── ADMIN AUDIT LOGS RLS ──
CREATE POLICY audit_logs_admin_read ON public.admin_audit_logs
    FOR SELECT TO authenticated
    USING (public.is_admin(ARRAY['super_admin', 'analyst']));

-- Grant proper schema usage
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT SELECT ON public.subscription_plans TO anon, authenticated;
GRANT SELECT ON public.subscription_plan_versions TO anon, authenticated;
GRANT SELECT ON public.plan_entitlements TO anon, authenticated;
GRANT SELECT ON public.user_subscriptions TO authenticated;
GRANT SELECT ON public.subscription_usage TO authenticated;
GRANT SELECT ON public.payment_orders TO authenticated;
GRANT SELECT ON public.payment_transactions TO authenticated;
