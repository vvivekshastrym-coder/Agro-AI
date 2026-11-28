# Drone Services

Drone Services is available through the Android app at **More → Drone Services**. It is not linked from the public website. The backend additionally requires a signed-in Agro AI user and a Firebase App Check token issued to the installed Android app for every `/api/drone` request; a browser header alone cannot grant access.

## Approval and privacy

- Provider applications remain private and unbookable until a Super Admin approves them. The admin must mark the required credentials and, for a company, business documents as verified.
- The farmer directory requires an active approved provider, current certificate (when an expiry is supplied), an active suitable drone, matching service area and availability. It returns no phone number, identity document, certificate scan, bank details or internal review notes.
- Verification documents are stored in the private `agro-drone-private` Supabase Storage bucket. The backend creates the bucket as private on first upload, validates file signature/type and size (10 MB maximum), and issues five-minute signed review links only to Super Admins.
- Internal approval does not replace statutory aviation/drone operating permissions. The approval UI asks reviewers to affirm document checks; it does not independently verify government credentials.
- Booking amounts come from the provider's configured per-acre price and minimum. Provider/day and drone/day partial unique indexes prevent concurrent active bookings on the same date. The provider marks a job complete, the farmer confirms it, and only then can the farmer review it.

## Production setup

1. In Firebase App Check, register the Android app `com.agroai.kisan` with Play Integrity and enable the Android provider. The deployed backend validates App Check JWT signature, audience, issuer, expiration and Android app ID.
2. Ensure production has the matching Firebase Android configuration and Play Integrity API enabled for the Firebase/Google Cloud project.
3. Ensure the backend has a production Postgres URL plus `SUPABASE_URL` and `SUPABASE_SECRET_KEY` (or `SUPABASE_SERVICE_ROLE_KEY`). The database user needs DDL rights for the one-time additive migration. On the first production FastAPI initialization, the backend applies `backend/migrations/drone_services.sql` under a Postgres advisory lock and records `drone_services_v1`.
4. Make sure at least one existing Agro AI user has the Super Admin role before using `/admin` → **Drone Operations**.
5. Build and install the Android app using `npm run mobile:sync`; the app bundle is emitted to `agro-ai-app/dist` and synchronized to Capacitor.

## Current scope

Implemented: application drafts/submission and status, individual/company/co-pilot applications, private verification documents, Super Admin manual application registration and review, explicit provider activation/suspension, company role invitation/confirmation and Super Admin approval, approved-provider search, configured quotes, farmer booking requests, provider status transitions, completion confirmation, and verified-booking reviews.

Not yet implemented: payment collection/refunds/settlements, dispute resolution, push/SMS notifications, document malware scanning, overlap-level time-slot scheduling (current collision protection is per calendar day), multiple-drone entry in the applicant form, a company-facing member/fleet management portal, and a production Android release build. The booking API does not claim payment was collected. These capabilities need gateway and operational policy configuration before they can be represented as live.
