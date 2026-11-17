# Agro AI Zero Trust and Data Integrity Audit

**Date:** 2026-11-17  
**Scope:** Local source review of the web/mobile front end, FastAPI backend, Supabase SQL, and existing security tests. No live Supabase project, production API, cloud account, or production database was accessed.

## Executive summary

The local source audit found and fixed several high impact integrity issues: a known fallback JWT signing key, an unauthenticated Google session exchange that trusted caller supplied identity fields, a payment flow that fabricated provider order IDs and could accept payments without a configured secret, unsigned webhooks, a support endpoint that converted an unverified reference into an active subscription, and startup seeding of invented business records. These changes have regression tests.

This is a partial source audit, not a production certification. Database policies were not exercised against PostgreSQL, and cloud configuration, live payment webhook configuration, backups, monitoring, real-data provenance, and production records remain unverified. Do not treat the platform as production-ready for significant personal or payment data based on this audit alone.

## Architecture observed

- Browser and mobile clients include the root application and a separate Agro AI app surface.
- The API is a FastAPI backend using SQLAlchemy with a local SQLite fallback and optional PostgreSQL/Supabase configuration.
- Supabase is used for client authentication/data access in the newer app surface and has SQL migration sets at the repository root and under `agro-ai-app/`.
- Payments use Razorpay-related backend flows; administrative actions and payment-support workflows are in the FastAPI admin router.
- The repository has separate local `.env` files and SQLite databases. Environment files and databases are ignored by Git; a tracked-file check found none of the inspected `.env` files.

## Findings and remediation

| ID | Severity | Finding and evidence | Fix / verification |
|---|---|---|---|
| AUTH-001 | Critical | `backend/app/auth/deps.py` supplied a hardcoded JWT signing secret when `SERVER_SESSION_SECRET` was missing. Anyone who knew the repository could mint trusted `agro-ai-local` tokens. | Removed the shared default. Development now uses an unpredictable process-local secret; production fails closed if the configured secret is absent or shorter than 32 characters. Tokens require expiry and standard `iat`/`nbf` checks. Regression suite passed. Set and rotate a unique production secret before deploying. |
| AUTH-002 | Critical | `/api/auth/google-session` in `backend/app/routers/auth.py` accepted arbitrary email, subject, and role fields without verifying an identity token, then issued a trusted backend JWT. | The exchange now requires a valid bearer identity already verified by `get_current_user`; caller supplied profile claims are ignored. The browser sends the verified Supabase access token for initial exchange and its current backend token for renewal. Forged unauthenticated requests are rejected in regression tests. |
| AUTH-003 | High | `/api/auth/guest-session` reused `farmer_guest` with hardcoded contact details, so independent anonymous visitors shared the same authorization subject and data ownership boundary. | Each guest session now receives a distinct UUID, no invented email/phone, and a one-hour token. Tests confirm distinct subjects and expiry. |
| PAY-001 | Critical | `/api/admin/payments/orders/{id}/assist-activate` marked an order paid, created a synthetic `staff_assisted` success transaction (including a generated reference when none was supplied), and activated a subscription from staff notes/UTR alone. | The endpoint now records a blocked-attempt audit event and returns 409 until provider reconciliation establishes payment success. It does not change the order, transaction ledger, or subscription. The payment-support regression test asserts those invariants. |
| PAY-002 | Critical | `create-order` fabricated `order_*` provider IDs; payment verification only checked a signature when a secret happened to exist; webhook signatures and event IDs were optional. | Checkout now creates a real Razorpay order server-side and fails closed without API credentials. Verification validates the checkout HMAC and fetches the provider payment, requiring captured status plus matching order, amount, and currency. Webhooks require the raw-body HMAC and provider event ID, deduplicate by that ID, validate captured payment/order/amount/currency, and persist only minimal event identifiers. Isolated tests mock the provider and assert signature enforcement/idempotency. |
| DATA-001 | High | `backend/app/seed.py` ran `create_all()` during import and its purported fake-data purge deleted whole business tables without identifying test rows. | Removed schema mutation and disabled the destructive cleanup. The command now refuses and explains that records cannot be safely classified. |
| DATA-002 | High | `backend/app/routers/mart.py` and `marketplace.py` automatically inserted hard-coded pilot farmers, listings, inventory, sellers, prices, and service regions when tables were empty. | Fixture seeding now requires both an explicit `ALLOW_DEMO_SEED=1` and a development/test environment. Production is explicitly tested to leave those tables unchanged. |
| DATA-003 | High | Admin aggregates counted test-user orders, all `success` transactions (including non-provider/manual rows), expired subscriptions, and test-user diagnosis/farm records. The dashboard also reported the webhook as active without checking its configuration. | Aggregates now exclude test users, require paid Razorpay orders with provider payment IDs, and exclude expired subscriptions. Webhook status says configured/not configured, with a matching neutral/amber dashboard indicator. |
| DB-001 | Medium | Production/staging startup called `Base.metadata.create_all()` and a schema-sync routine, allowing automatic database schema mutation outside reviewed migrations. | Automatic create/sync is now skipped for production and staging; local/test bootstrap remains available. |
| TEST-001 | Medium | Backend tests failed to collect from the backend project directory because `auth.py` imported `backend.app.services...` as an absolute path. | Changed to a package-relative import. The focused test suite now collects and passes. |
| TEST-002 | Low | An OTP test module imported/monkeypatched the backend using repository-root-only module paths. | Standardized imports and mock targets to the backend package path so the complete test suite runs from `backend/`. |

## Security controls found in source

- The existing security test suite asserts RLS is enabled on at least 55 tables in `supabase_schema.sql`; this is static text coverage, not a live policy behavior test.
- Farmer profile, farm, and crop migrations contain ownership policies. Payment/admin migration defines RLS and role helpers. Backend tests cover selected logistics ownership and admin authorization paths.
- Static file blocking and several HTTP security headers are present in `backend/app/main.py`.
- Production and staging now rely on reviewed schema migrations rather than startup auto-sync. Synthetic catalog seeders are gated to explicitly opted-in dev/test environments.

## Remaining risks and incomplete verification

1. **Live Supabase database:** The connected `agro-ai-app` Supabase project reports `INACTIVE`; a read-only migration-history request timed out. I did not reactivate it because that can incur compute charges. Source inspection found RLS enabled on all 55 tables in `supabase_schema.sql`; 37 have no explicit policy there, so they depend on default deny and require access/grant verification. The separate `agro-ai-app` migration set defines policies for its six own tables. Neither set was exercised against PostgreSQL identities. Validate grants, policies, storage, views, and production schema drift in an active disposable staging project with two-user BOLA tests.
2. **Supabase SQL migration state:** Root `0003` creates `public.is_admin()` as `SECURITY DEFINER` with a pinned search path but does not explicitly revoke default `PUBLIC` execute access. Its body only returns an authorization boolean based on the caller's own `auth.uid()`, but explicit grants should be applied in a follow-up migration. `0005` creates an admin metrics view without `security_invoker`; it also does not consistently exclude test rows and provider-unverified revenue. The FastAPI dashboard has been hardened, but the SQL view still needs a migration and PostgreSQL verification. Supabase CLI is not installed in this environment, so no migration was generated or applied.
3. **Authentication operations:** The custom phone OTP store is process-local, so multi-worker deployments can lose challenges and do not share lockout state. Login throttling, MFA for admins, refresh/session revocation, device management, and secret rotation operations were not verified. Google token validation now requires an explicit `GOOGLE_CLIENT_ID(S)` allowlist; configure the exact deployed client IDs.
4. **Payment provider operations:** The code now fails closed and validates provider state, but the configured Razorpay account, actual test/live keys, webhook URL registration, event subscriptions, refunds, and provider sandbox lifecycle have not been tested. The connected Vercel project list request returned 403 because this session lacks access to the team scope; no cloud configuration or deployment settings were read or changed.
5. **Data provenance:** Government-scheme text and some market reference data remain static. Their source citations, retrieval timestamps, expiry behavior, and production record provenance were not established. No SQLite data contents or live production records were inspected.
6. **Infrastructure and operations:** TLS termination, cloud IAM, secrets store, firewall/WAF, storage privacy, backups, recovery objectives, alert delivery, incident response, CI scans, and deployment access remain unverified.
7. **Independent assessment:** No active penetration test was performed. Arrange an authorized independent review against OWASP ASVS/API Top 10 before handling substantial identity documents, location data, or payments.

## Verification performed

Commands run from `backend/`:

```text
pytest -q
150 passed, 382 warnings
```

The suite uses an isolated temporary SQLite database. It does **not** verify live PostgreSQL RLS or production services. Warnings include deprecated FastAPI lifecycle hooks, SQLAlchemy APIs, and `datetime.utcnow()` calls.

The admin dashboard source also passed `npm run build` (TypeScript compile and Vite build). The root app's local Vite URL returned HTTP 200 at `http://127.0.0.1:5173/`.

## Production readiness

**Not established.** The critical local fixes reduce concrete account-forgery and payment-ledger risks, but the unresolved database, provider, production-data, and infrastructure checks above must be completed in isolated staging and reviewed before release.
