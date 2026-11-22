# AGRO AI — COMPLETE WEBSITE QUALITY ASSURANCE AUDIT

**Audit date:** 20 November 2026  
**Target:** [https://www.agroai.live](https://www.agroai.live)  
**Environment:** Production website, existing signed-in Chrome session  
**Scope:** Read-only exploratory interaction audit. No profile edits, purchases, message submissions, uploads, sign-out, account deletion, or subscription changes were made.

## Executive summary

The production site loaded and exposed its home dashboard and major modules. The account panel identified an authenticated Google session, and Plans displayed active free farmer access. Agro GPT loaded without a visible login banner in the captured page view; however, Chrome’s accessibility tree retained the login-warning text on several unrelated routes. This is a confirmed inconsistency in the page’s accessibility representation, but this run did **not** confirm that a visible warning blocked the signed-in user or that a chat request fails. The root cause is unconfirmed.

Inputs Compare is a confirmed incomplete view: after opening it from More and selecting **Fertilizer**, its page contained only the title, description, and four category controls, with no comparison products, empty-state message, or loading/error status. This makes the advertised comparison feature unusable in the inspected session.

The audit was limited by the production environment and the available native Chrome automation surface. It did not complete every listed page, element, viewport, API inspection, or authentication flow. Counts below describe only actions and views observed in this run, not total site coverage.

## Test results dashboard

| Measure | Result |
|---|---:|
| Distinct app views inspected | 9 |
| Interactive controls activated | 13 |
| Confirmed working navigation/modal controls | 10 |
| Confirmed failed or incomplete controls/views | 1 incomplete feature view |
| Inconclusive observations | 1 (Agro GPT warning in accessibility tree) |
| Blocked/not executed | Not exhaustively enumerated; see scope limits |
| Critical / High confirmed bugs | 0 |
| Medium confirmed bugs | 1 |
| Low confirmed bugs | 1 accessibility concern |
| Security findings confirmed | 0 |
| Responsive sizes measured | 1 desktop browser window only |
| Performance metrics measured | 0 |

“Working” here means the expected page or modal appeared for the specific activated control. Controls not individually activated are not counted as passed.

## Website structure discovered

Primary navigation observed: Home, Diagnose, Agro GPT, Weather, Mandi, and More. Header controls observed: Plans, language selector, and Account. The More view listed:

- Agro AI Mart; Sell on Agro AI Mart; Account & Security; Membership & Plans; Pest Radar; Inputs Compare; Logistics; Drone Marketplace; Satellite Twin; Carbon Credits; Auto Insurance; Soil DNA Lab; Farm Passport; Government Schemes; Alternative Credit; My Reports.

The audited routes/views included Home (`/`), Diagnose (`/diagnose`), Agro GPT (`/agrogpt`), Weather (`/weather`), Mandi (`/mandi`), More services (in-app view), Inputs Compare (in-app view), Plans (`/plans`), and Account (in-app view). The account view exposed profile/security details, export and delete controls, policy links, admin-console link, cookie and age/consent controls, and sign out. Destructive and account-changing controls were not activated.

## Page-by-page and interaction results

### Home — `/`

- Dashboard rendered with greeting, weather/spray summary, feature cards, daily report, recent report, and bottom navigation.
- Tapping the Diagnose, Weather, Mandi, More, Plans, and Account controls opened their respective views during this run.
- A WhatsApp notification summary was visible in the signed-in dashboard. Its personal destination is intentionally omitted from this report.
- Visual observation: logo, header, cards, and bottom navigation were visible in the desktop screenshot. No responsive conclusion can be drawn from this single desktop viewport.

### Diagnose — `/diagnose`

- Diagnosis view rendered a sample/recent Tomato leaf-curl result, confidence, advice, Organic/Chemical controls, Save report, and Share WhatsApp controls.
- Choose photo, Analyze, advice tabs, save, and share were not individually tested. Uploading or saving/sharing production data was outside this read-only run.
- No conclusion is made about the accuracy of the displayed diagnosis or advice.

### Agro GPT — `/agrogpt`

- The view rendered language choices (English plus eight Indian languages), History, New chat, composer, Speak instead, Talk to Agro GPT, and suggested prompts.
- Direct navigation from the signed-in app session returned the same usable-looking GPT screen; the account view continued to identify the user as signed in.
- **Evidence inconsistency:** the accessibility tree included “Please log in to continue using AgroGPT…” on the GPT page and also on Home, Diagnose, Weather, Mandi, Plans, and Account. In the captured GPT screenshot, that warning was not visibly displayed. Thus the warning’s accessibility exposure is confirmed, but a visible false-login toast, denied access, or failed authenticated chat is not confirmed in this run.
- Composer focus was not successfully verified, and no question was submitted. History, New chat, language switching, voice controls, suggested prompts, and backend response were not tested.

### Weather — `/weather`

- Location search, current-location, refresh, “Use as Logistics Pickup”, current conditions, forecast, and spray advisory were exposed.
- Current conditions and a 7-day forecast were populated. Search, refresh, GPS and logistics handoff were not activated; no claims about those actions are made.
- The page disclosed a device-derived location in the UI. Its value is omitted here. Location-permission behavior and data handling were not independently tested.

### Mandi — `/mandi`

- State, district, commodity, date, market search, CSV, refresh, market directory, and Load More controls were exposed.
- The directory showed 15 of 52 markets. The selected market displayed an explicit “No current price data available” state for the selected commodity/date. This is a data-availability message, not by itself a confirmed application defect.
- Filters, search, CSV export, refresh, market selection, and Load More were not individually exercised.

### More services and Inputs Compare — in-app views

- More displayed the module inventory listed above. Its **Inputs Compare** card opened the Inputs Compare view.
- Inputs Compare exposed All, Fertilizer, Pesticide, and Seeds controls. After selecting **Fertilizer**, the page still exposed only the heading/description and tabs; no products, empty-state explanation, or error/loading status appeared.
- **Bug AGRO-QA-01 (Medium): Inputs Compare has no visible comparison result.** Reproduction: sign in → More → Inputs Compare → Fertilizer. Expected: fertilizer listings or a clear empty/error state. Actual: category controls remain, but the product area is empty with no status. Network evidence was unavailable, so the backend/data cause is unknown.
- More service cards were not all individually opened. Features requiring bookings, applications, account edits, or a paid/state-changing flow were left untouched.

### Plans — `/plans`

- Page displayed “Free Farmer Access”, ACTIVE status, unlimited feature quotas, and a statement that online payment is not active and features are free for registered farmers.
- This is inconsistent with the login-warning text present in the Agro GPT accessibility tree. It supports the concern in AGRO-QA-02 but does not prove a denied chat request.
- Cancel / Unsubscribe was visible and deliberately not activated.

### Account — in-app view

- Account panel displayed signed-in state, farm profile summary, Google sign-in method, two-factor status, active-session count, policies, and account actions.
- Account panel therefore provides direct UI evidence of the signed-in state used when inspecting Agro GPT.
- Export, Delete account, Sign out, cookie/age settings, and admin-console controls were not activated. No logout-clearance or authorization conclusion is available.

## Confirmed and possible bugs

### AGRO-QA-01 — Inputs Compare renders no products or empty-state status

- **Severity:** Medium
- **Page/URL:** Inputs Compare, reached from More; underlying address remained `/mandi` in Chrome.
- **Element:** Fertilizer category button and comparison results area.
- **Steps:** Sign in; open More; open Inputs Compare; choose Fertilizer.
- **Expected:** Product comparisons, or a clear “no listings” / service-error state.
- **Actual:** Heading, description, and category controls only; no comparison results or status before or after category selection.
- **Evidence:** Chrome accessibility snapshots after page opening and after selecting Fertilizer showed the same title/description/category-control set with no result items. No screenshot file was exported.
- **Console/network:** Not available in this audit.
- **Likely investigation:** `loadInputsProducts()` and Inputs Compare view/render code in `index.html`; inspect its API response and failure/empty-state handling. This is a lead, not a proven cause.
- **Recommended fix:** Show products on a successful response and a visible empty/error/retry state otherwise; ensure category selection updates both active state and results.

### AGRO-QA-02 — Agro GPT login-warning text is exposed outside the authenticated context (inconclusive user-facing defect)

- **Severity:** Low pending reproduction; raise to High only if it visibly blocks authenticated chat.
- **Page/URL:** `/agrogpt`; same warning text appeared in accessibility snapshots for unrelated views.
- **Element:** `agroGptLoginBanner` / login-warning text.
- **Steps:** Use the existing signed-in Google session; inspect Account for signed-in state and active plan; open `/agrogpt`.
- **Expected:** Authenticated interface without an unauthenticated warning.
- **Actual:** Warning text was present in Chrome’s accessibility tree across routes, but absent from the captured visible GPT screenshot. Chat submission was not performed, so false denial is not established.
- **Evidence:** Account view showed signed-in state; Plans showed active free access; GPT AX snapshot included the login text; GPT screenshot did not visibly show it.
- **Console/network:** Not available; no chat request was made.
- **Code clue (not root-cause proof):** Local `index.html` defines `isRegisteredFarmer()` near line 4280, `updateAgroGptAccessUI()` near line 4340, and the banner at lines 1092/4365. `sendChat()` guards on that legacy helper near line 5569 and fetches `/api/agro-gpt/chat` near line 5608. The live network behavior and exact failing branch were not captured; local source may not match the deployed build.
- **Recommended investigation:** Capture live DOM visibility, `isRegisteredFarmer()` result, Supabase session state, and the chat request’s status/response in DevTools on a safe test account. Do not remove the gate until the true auth/API contract is established.

### AGRO-QA-03 — More-service cards lack button/link semantics in the accessibility tree

- **Severity:** Low; accessibility issue.
- **Page:** More services.
- **Element:** Service cards such as Inputs Compare.
- **Expected:** Interactive cards should be announced as links or buttons and be keyboard operable.
- **Actual:** The accessibility snapshot represented the service cards as generic `group` elements with text, rather than button/link roles. One was activatable through the automation surface, but keyboard operation and focus indication were not tested.
- **Evidence:** AX snapshot for More listed each card as `group`; no button/link role was provided.
- **Recommended investigation:** Inspect semantic markup and keyboard handlers for More service cards; use native anchors/buttons with visible focus styling.

## Authentication, onboarding, security, accessibility, responsive and performance

- **Authentication:** Existing session was already signed in with Google. Google login, Phone OTP, guest entry, registration, onboarding, session refresh/expiry, logout, and callback flows were not exercised.
- **Onboarding:** Not tested; would create or modify production farmer data.
- **Protected data/security:** No cross-user, role-bypass, subscription bypass, or protected-data tests were attempted. No security issue was confirmed. UI claim of encryption/privacy was not independently verified.
- **Accessibility:** Basic Chrome AX inspection was possible. AGRO-QA-03 is the one confirmed semantic concern. Keyboard-only flow, contrast, focus order, dialog focus management, and screen-reader testing were not completed.
- **Responsive/UI:** One desktop-sized Chrome window was visually inspected. The requested mobile/tablet/laptop/large-desktop viewport matrix was not available through this audit surface. No mobile conclusion is drawn.
- **Performance:** No DevTools Network/Performance trace or Web Vitals was captured. Load times, API latency, layout shift, and asset sizes remain unmeasured.
- **Console/API:** Browser DevTools were not available through the accessible automation surface. No request URLs/status codes, console errors, or response payloads are claimed.

## Prioritized fix plan

1. **Inputs Compare/data:** Inspect `loadInputsProducts()` and the response/render path; add visible loading, error, and empty states; verify category filtering.
2. **Agro GPT authentication:** On a safe test account, capture auth state and composer/message behavior together with `/api/agro-gpt/chat` response. Inspect `isRegisteredFarmer()`, Supabase session restoration, and bearer-token exchange before changing access logic.
3. **Accessibility semantics:** Make More cards keyboard-operable and exposed as buttons/links with focus indication.
4. **Complete the remaining module/API audit:** Use a preview deployment and dedicated test account for stateful forms, OTP, onboarding, upload, and service booking. Inspect network/console on each relevant flow.
5. **Responsive/performance pass:** Test all requested viewport sizes and collect DevTools performance/network evidence.

## Blocked and untested areas

The following were not tested or only partially inspected: every More module other than Inputs Compare; all GPT history/new-chat/voice/message behavior; diagnosis upload/analysis/save/share; Mandi filter/search/export/load-more behavior; weather search/GPS/handoff; Google/OTP/guest/login/logout/onboarding/refresh/expiry; forms and upload restrictions; subscription/cancellation/payment flows; notification settings; private-data isolation; console/network/API behavior; mobile/tablet and additional desktop sizes; performance metrics; full keyboard and assistive-technology audit. Production writes and irreversible actions were intentionally excluded.

No source files or production data were modified by this audit.
