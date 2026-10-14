# Agro AI — Platform Metrics Registry & Governance Specification

This document serves as the authoritative single source of truth for all quantitative metrics rendered on the Agro AI Administrative Console, Executive Reporting APIs, and Farmer Dashboards.

## Core Governance Rules

1. **Zero Synthetic / Mock Data**: No metric may ever fall back to hardcoded demo arrays, randomized generators, or simulated constants.
2. **Authoritative Calculation**: All metric counters, monetary sums, and volumetric figures must be computed strictly via server-side SQL queries on the active PostgreSQL database (`kisanai.db` in SQLite test runtime).
3. **Genuine Zero vs. Unavailable**:
   - A metric returns `0` only if a table is queried successfully and genuinely contains zero matching rows (e.g., 0 open disputes).
   - If a backend service, data lake, or external provider (e.g., satellite index or APMC feed) is offline or unreachable, the metric status must return `"Unavailable"` (`null`), never `0`.
4. **Temporal Standards**: All timestamps are tracked in UTC and localized to **Indian Standard Time (IST, UTC+5:30)** for business reporting.
5. **Monetary Precision**: All financial amounts are stored as integer minor units (paise in INR). Display values are formatted as `₹(amount_minor / 100.0)`.

---

## Metric Registry

| Metric Name | Display Label | Source Table / View | SQL Definition / Formula | Filters & Status Rules | Currency / Unit | Time Zone |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `registered_users` | Total Registered Accounts | `users` | `COUNT(id)` | All non-deleted rows (`is_active = true`) | Integer | UTC / IST |
| `total_farmers` | Real Registered Farmers | `users` | `COUNT(id)` | `role = 'farmer' AND is_active = true` | Integer | UTC / IST |
| `verified_users` | Verified Farmer Profiles | `users` | `COUNT(id)` | `is_verified = true` | Integer | UTC / IST |
| `total_acres` | Verified Farmland (Acres) | `farms` | `COALESCE(SUM(total_acres), 0.0)` | Valid farm boundaries linked to registered users | Decimal (Acres) | UTC / IST |
| `ai_diagnoses_count` | AI Crop Diagnoses Run | `diagnosis_reports` | `COUNT(id)` | Genuine Gemini Vision pathology analyses performed | Integer | UTC / IST |
| `active_subscriptions` | Active Memberships | `user_subscriptions` | `COUNT(id)` | `status = 'active' AND current_period_end > NOW()` | Integer | UTC / IST |
| `total_orders` | Subscription Orders | `payment_orders` | `COUNT(id)` | All customer subscription checkout orders | Integer | UTC / IST |
| `total_revenue_inr` | Collected Subscription Revenue | `payment_transactions` | `COALESCE(SUM(amount_minor), 0) / 100.0` | `status = 'success'` | INR (₹) | UTC / IST |
| `active_broadcasts_count` | Published Advisories | `broadcast_items` | `COUNT(id)` | `status = 'approved'` | Integer | UTC / IST |
| `pending_approvals_count` | Pending Approvals Queue | `broadcast_items`, `admin_access_requests` | `COUNT(pending broadcasts) + COUNT(pending staff requests)` | Items awaiting Head Super Admin review | Integer | UTC / IST |
| `mart_active_sellers` | Approved Mart Farmers | `mart_seller_profiles` | `COUNT(id)` | `status = 'APPROVED'` *(Stage 3 Mart)* | Integer | UTC / IST |
| `mart_live_listings` | Live Fresh Produce Listings | `mart_listings` | `COUNT(id)` | `status = 'APPROVED' AND stock_quantity > 0` *(Stage 3 Mart)* | Integer | UTC / IST |
| `mart_order_value_inr` | Cumulative Mart Order Value | `mart_orders` | `COALESCE(SUM(total_minor), 0) / 100.0` | `status = 'COMPLETED'` *(Labelled as Order Value, not revenue)* | INR (₹) | UTC / IST |

---

## SQL View Definition (Supabase / Postgres)

```sql
-- Production SQL View for Real-time Dashboard Overview
CREATE OR REPLACE VIEW view_admin_platform_overview AS
SELECT
    (SELECT COUNT(*) FROM users WHERE is_active = true) AS registered_users,
    (SELECT COUNT(*) FROM users WHERE role = 'farmer' AND is_active = true) AS total_farmers,
    (SELECT COUNT(*) FROM users WHERE is_verified = true) AS verified_users,
    (SELECT COALESCE(SUM(total_acres), 0.0) FROM farms) AS total_acres,
    (SELECT COUNT(*) FROM diagnosis_reports) AS ai_diagnoses_count,
    (SELECT COUNT(*) FROM user_subscriptions WHERE status = 'active' AND current_period_end > NOW()) AS active_subscriptions,
    (SELECT COUNT(*) FROM payment_orders) AS total_orders,
    (SELECT COALESCE(SUM(amount_minor), 0) / 100.0 FROM payment_transactions WHERE status = 'success') AS total_revenue_inr,
    (SELECT COUNT(*) FROM broadcast_items WHERE status = 'approved') AS active_broadcasts_count,
    (SELECT COUNT(*) FROM broadcast_items WHERE status = 'pending_approval') +
    (SELECT COUNT(*) FROM admin_access_requests WHERE status = 'pending') AS pending_approvals_count,
    NOW() AS metrics_computed_at;
```
