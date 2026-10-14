-- ==============================================================================
-- Migration: 0005_clean_and_metrics.sql
-- Description: Adds is_test flag to users and creates authoritative SQL view
--              for real-time platform metrics and reporting governance.
-- ==============================================================================

-- 1. Add is_test flag to users
ALTER TABLE IF EXISTS users 
ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_users_test_active ON users (is_test, is_active);

-- 2. Authoritative SQL View for Admin Dashboard Overview
-- Eliminates client-side synthetic metric generation; purely derived from real rows.
CREATE OR REPLACE VIEW view_admin_platform_overview AS
SELECT
    (SELECT COUNT(*) FROM users WHERE is_test = FALSE AND is_active = TRUE) AS registered_users,
    (SELECT COUNT(*) FROM users WHERE role = 'farmer' AND is_test = FALSE AND is_active = TRUE) AS total_farmers,
    (SELECT COUNT(*) FROM users WHERE is_verified = TRUE AND is_test = FALSE AND is_active = TRUE) AS verified_users,
    (SELECT COALESCE(SUM(total_acres), 0.0) FROM farms) AS total_acres,
    (SELECT COUNT(*) FROM diagnosis_reports) AS ai_diagnoses_count,
    (SELECT COUNT(*) FROM user_subscriptions WHERE status = 'active' AND current_period_end > NOW()) AS active_subscriptions,
    (SELECT COUNT(*) FROM payment_orders) AS total_orders,
    (SELECT COALESCE(SUM(amount_minor), 0) / 100.0 FROM payment_transactions WHERE status = 'success') AS total_revenue_inr,
    (SELECT COUNT(*) FROM broadcast_items WHERE status = 'approved') AS active_broadcasts_count,
    (SELECT COUNT(*) FROM broadcast_items WHERE status = 'pending_approval') +
    (SELECT COUNT(*) FROM admin_access_requests WHERE status = 'pending') AS pending_approvals_count,
    NOW() AS metrics_computed_at;

COMMENT ON VIEW view_admin_platform_overview IS 'Authoritative platform metrics computed strictly from verified database rows without mock fallbacks.';
