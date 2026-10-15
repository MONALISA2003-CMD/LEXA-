# LEXA Product, UX, Architecture & Intelligence Research Blueprint

**Research snapshot:** 13 October 2026  
**Scope:** Product intent, current experience, authentication, module completeness, backend/database integration, phased delivery, Python intelligence and multi-model routing.  
**Source of truth for product architecture:** the original Markdown files in `docs/`, current source at commit `010129d461bac0eef242a858e4d8d0210cf64d3c`, read-only Render deployment/log inspection, and read-only schema/migration inspection of the canonical Neon branch.  

> This is a research and build plan, not a claim that every module is production-ready. Live database and hosting observations are snapshots. No database mutation, production deployment, or source push was performed during this research.

---

## 1. Executive conclusion

LEXA should be built as a **reliable operational workspace first, with a governed intelligence layer second**. The current system already contains real foundations—identity, tenancy, a product catalogue, stock ledger and workflows, commerce, accounting, compliance and descriptive analytics—but their maturity varies significantly. Several visible navigation items are still placeholders, some modules are aliases of the same page, and the current session bootstrap can turn a client/server request-contract mismatch into a whole-workspace outage message.

The next work should not be “add more modules” indiscriminately. It should be a sequence of tiny vertical increments where each increment delivers a coherent user task, has API/database acceptance tests, and can be demoed on a real phone.

### The five decisions that will save the most time

1. **Stabilise source, deployment and session contracts before adding features.** Correct the Next.js Vercel root/build command, repair session refresh and test the live auth flow end to end.
2. **Treat each visible page according to its real maturity.** Finish Products, Inventory and Sales/Payments where core source already exists; do not replace those foundations with rewrites. Make Purchasing, Customer Management, Administration, Settings and Intelligence real product areas in sequence.
3. **Make every screen communicate its data state honestly.** An API error is not an empty list; an unloaded KPI is not UGX 0; the application shell cannot say “Online” when no health signal was checked.
4. **Use one shared responsive design system and common workflow components.** Each module should have standard list/detail/create/action patterns and explicit loading, empty, validation, permission, offline and success states.
5. **Use Python and deterministic business services for calculations; use LLMs for language and bounded reasoning.** Start with read-only Ask LEXA and evidence-linked summaries. Allow controlled actions only after the model proposes an action, the backend validates it, the user approves it, and a normal application command executes it.

The original workspace-convergence document already describes the right product principle: LEXA is “a business workspace, not an ERP maze.” Keep this principle and consolidate scattered phase notes into one versioned product brief and acceptance standard.

---

## 2. Evidence-led state of the current product

### 2.1 What the screen recording shows

The 22.9-second mobile recording shows a recognisable product shell, but also enough friction to explain why it feels unfinished:

- A large global “LEXA is temporarily unavailable” message occupies the workspace, while the page underneath continues to display numbers and empty states.
- Sign-in feedback such as “Those sign-in details don’t match” appears in the same session in which the shell has declared a service issue. The two messages communicate different diagnoses and leave the user unsure what to do.
- Dashboard KPI cards display zero values even when the application is failing to establish a workspace/session. The user cannot tell “there are no sales” from “sales did not load.”
- Inventory has zero-valued cards and “No stock rows” while the session/service warning is present. That is misleading because the UI has not established that an authoritative empty result was returned.
- The Sales page is a long, multi-purpose form/tab workspace and requires too much scrolling on a narrow viewport.
- Purchasing shows a foundation/coming-next pattern rather than a purchase-order workflow.
- Customers reuses the Sales & Commerce surface rather than behaving like an independent customer directory and customer account workspace.
- Small labels, compressed mobile tabs/cards, and the fixed bottom navigation make the interface feel dense. Key operational controls do not get the breathing room expected on a phone.

The recording is useful evidence of how the current release feels, but it does not prove database state or every endpoint’s health. The hosting logs and source are needed for that diagnosis.

### 2.2 Source maturity by route

| Route/module | Current source evidence | Current maturity assessment | Next work |
|---|---|---|---|
| Home / Command Centre | Requests commerce dashboard, analytics, balances, adjustments, counts, transfers and readiness | Live-data surface exists; failure/partial-load semantics need fixing | Phase 0 reliability, then truthful KPI/data states |
| Login and session | Sign-in, workspace selection, in-memory access token and refresh-cookie pattern exist | Core flow present; refresh contract is mismatched | Fix first, add full auth E2E tests |
| Registration | Creates a workspace, has idempotency support, and logs in after registration where flow permits | Real foundation; onboarding is thin | Add post-registration setup and recoverable errors |
| Products | Product/variant, SKU, barcode, prices and inventory visibility APIs/pages exist | Substantial working foundation | Complete E2E workflows, validation, search/detail and import later |
| Inventory | Stock, ledger, adjustments, counts, transfers, locations and integrity are represented | Substantial working foundation | Prove each state transition end to end; improve mobile interaction |
| Sales | Route aliases to commerce UI; commerce UI has sell, channels, receivables, reconciliation, returns and history | Much of the core source exists, but experience is too broad/long | Extract a focused POS flow and keep secondary tasks in their own routes/tabs |
| Customers | Route is a 74-byte alias to commerce | Not an independent customer product area | Build customer list, profile, history, balance and account actions |
| Purchasing | Uses `ModuleFoundation` with a list of future capabilities | Placeholder, not functional purchasing UX | Build supplier → PO → receiving vertical slice after source/schema reconciliation |
| Accounting | Accounts, periods, journals, trial balance and statements loaded from APIs | Significant implementation present | Verify posting bridges, reversals, period locking and report correctness |
| Reports | Date range, KPIs, products/customers/inventory/branches and analytics refresh present | Descriptive BI foundation | Make metrics traceable and show projection freshness/source; add exports later |
| Compliance / EFRIS | Configuration, tax rates/configurations and fiscal-document surface exist | Foundation present; no claim of a real URA system-to-system integration | Clearly label manual/pending/live modes; only show provider-sourced fiscal facts |
| Administration | `ModuleFoundation` page | Placeholder | Member, roles, permissions, invitations, branch assignment and sessions |
| Settings | `ModuleFoundation` page | Placeholder | Profile, locale, timezone, currency and workflow defaults |
| AI Intelligence | `ModuleFoundation` page; no Brain router included in FastAPI app route registration | Placeholder despite persisted `brain_*` tables | Build a Python model gateway, safe read-only tools and evidence-grounded Ask LEXA |
| Invite | Page imports `acceptInvitation`, which is not exported by `apps/web/lib/api.ts`; FastAPI has no matching invite HTTP route | Broken feature contract | Implement invite create/accept/list/revoke end to end; don’t fake it or leave a dead form |
| Universal kernel / business engine | Technical foundation exists, but should be hidden from users | Internal infrastructure, not a product module | Keep internal; expose user outcomes through real modules |

The assessment is based on source routes/API calls and original documents—not on marketing labels. “Substantial implementation” means there is a real source/API surface that warrants verification; it does **not** mean production readiness has been proven.

### 2.3 Why LEXA felt “not available” even though Render was green

A concrete defect exists across the frontend/backend contract:

- `apps/web/lib/api.ts` attempts session restoration with `POST /api/v1/auth/refresh` and a `Content-Type: application/json` header, but it sends **no request body**.
- The same empty-body refresh call is made after a protected API request returns `401`.
- `apps/api/app/routes/auth.py` declares `refresh(body: RefreshRequest, ...)`. Although `refresh_token` is optional inside `RefreshRequest`, the **body model itself is required** by FastAPI when the parameter has no default. An absent body therefore fails request validation with `422` before token/cookie logic runs.
- The Render log snapshot on 13 October showed `/health` returning `200`, `/ready` returning `200`, then a burst of protected-route `401`s and `/api/v1/auth/refresh` `422`s at approximately 04:43 UTC. The volume included multiple IPs; not every entry can be attributed to this one user, but the response pattern matches the source defect exactly.
- `AppShell` catches a refresh failure and marks the authentication state as “unavailable”. The current shell then displays a generic service-unavailable banner, even where the proximate problem is a request validation error rather than a proven network or database outage.

**Most likely immediate failure:** the session-refresh request contract, not a proven Neon outage. The existing readiness `200` is evidence against diagnosing the incident as “the database is definitely down,” but readiness alone does not verify login, tenant scope, business queries or every DB object.

**Correct repair:** make the backend tolerate an omitted refresh body (`RefreshRequest | None = None`) and safely check it, while the browser always sends an explicit `{}`. Add a single-flight refresh so multiple concurrent `401`s do not all rotate the same refresh token; test refresh rotation under concurrent requests. Treat refresh `401` as expired/invalid session, `422` as a request-contract defect to alert/monitor, and network/`5xx` failures as service availability problems. Do not collapse them into one message.

### 2.4 Deployment and configuration risk

The project’s own `docs/DEPLOYMENT_RENDER_VERCEL.md` defines the intended split:

- Vercel: Next.js frontend, root directory `apps/web`, normal Next.js build/install defaults.
- Render: FastAPI service, root directory `apps/api`, `pip install -r requirements.txt`, `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Neon: sole PostgreSQL source of truth.
- Render Key Value/Valkey: cache/queue layer; not business truth.

The supplied Vercel log runs a root-level command that deletes `app/business-engine` and `app/kernel` before building and then errors at `app/invite/page.tsx` importing a missing `acceptInvitation` export. The import is also missing from the correct `apps/web/lib/api.ts`. There are therefore **two** problems: a source contract defect and a Vercel build-root/command mismatch. Removing directories at build time is a brittle workaround because the build result depends on destructive cleanup. Set the correct root and remove the custom `rm -rf` build command; separately decide route-by-route which UI pages should exist.

### 2.5 Source-to-live database drift is a first-class risk

A read-only query against canonical Neon (`LEXA`, branch `lexa-live`, database `neondb`) found the migration ledger records `020`, `021`, `022`, `023_phase2_identity_tenancy_authorization_foundation`, `023_phase4_purchasing_core`, `024_phase4_purchasing_security`, `025_phase4_purchasing_permissions`, `026_phase4_membership_branch_integrity` and `027_release_convergence`. The source tree has the 023 identity migration but does not contain the purchasing/security/permissions and 026/027 source migration files; its `migrations/README.md` still lists through migration 021.

That does **not** mean the live database is corrupt. It means the repository’s visible migration history is not a complete reproducible explanation of the live schema. It must be reconciled before schema-changing work. Do not reset the database, replay unknown migrations, or recreate objects by guesswork. Locate the authoritative SQL from the package/history that was applied, recover it into version control, compare the live schema and grants, and add a CI rule that fails when DB ledger entries have no checked-in migration source.

The `brain_*` tables and row-level tenant policies are already present in the canonical DB, but this is persistence foundation—not a running AI service. `apps/api/app/main.py` registers auth, organization, RBAC, catalog, inventory, kernel, commerce, finance and analytics routers; it does not register a Brain/model-inference router. The source package also needs an isolated migration test for `022_phase6a_brain_foundation.sql`, whose final RLS-policy SQL appears malformed in the source text. Verify this on a disposable Neon branch before editing or applying anything to live.

### 2.6 Vercel and Render are healthy in different ways

A successful Render deploy and `/ready` returning `200` do not prove the frontend builds. A successful Vercel build would not prove authentication or tenant queries work. We need independent gates for:

1. source compile/typecheck/build;
2. process health;
3. DB and cache readiness/canonical branch identity;
4. login, refresh, logout, multi-workspace selection;
5. one core business workflow;
6. mobile UX and failure-state checks.

A currently connected Vercel integration search did not return a LEXA project, so this research could not verify the live Vercel Project Settings or production environment values via that connector. The posted log and the repository’s own deployment guide are the available evidence; confirm Project Root Directory and build override in Vercel dashboard.

---

## 3. Product strategy and user model

### 3.1 Product promise

**LEXA gives an African small or medium business one trustworthy place to run daily operations, see its real numbers, and get evidence-backed advice.** The user should not have to understand internal kernels, ledgers, migrations, models, tokens or deployments to use it.

Start with the day-to-day work of a shop, distributor, service business or multi-branch operator:

- What do I have, where is it, and what is running out?
- What did I sell, what money did I collect, and what is still owed?
- What should arrive from suppliers and what do I need to pay?
- Is my stock, cash, reconciliation and accounting state correct?
- What needs my attention today?
- Can LEXA explain an issue and prepare a safe next step without taking uncontrolled action?

### 3.2 Primary personas

| Persona | Main job | Needs |
|---|---|---|
| Owner / proprietor | Know health of the business and approve important actions | Small number of high-confidence KPIs, exceptions, cash/receivables, branch switching, role administration |
| Cashier / sales operator | Sell quickly and accurately, accept payment and issue receipt | Barcode/search-first checkout, forgiving inputs, clear payment total/change, keyboard and touch affordances |
| Inventory/storekeeper | Keep balances right, receive stock, count and transfer | Scannable lists, filters by location, guided state transitions, variance review, a traceable ledger |
| Purchasing/procurement | Buy the right things and see what was received/owed | Suppliers, draft/approval PO, partial receiving, discrepancies, supplier history and payable bridge |
| Finance/accounting | Close periods, reconcile, review journals and financial statements | Balanced totals, reversals rather than silent edits, evidence trails and accounting periods |
| Branch manager | Manage the assigned branch without seeing other branches | Visible branch context, branch-scoped metrics and action rights |
| Administrator | Maintain members, roles, settings and access | Invitations, roles/permissions, sessions/devices, audit and configuration |
| Adviser / analyst | Investigate business questions | Read-only evidence-backed answers, date and branch filters, source links, safe export |

Do not build a different app for every persona. Use the same workspace and data concepts, but adapt navigation, default landing page and allowed actions by role.

### 3.3 Product principles

1. **Business outcomes over technical modules.** “Stock count” is a user outcome; “universal business engine” is implementation detail.
2. **Trust above animation.** Never claim a sale, receipt, transfer, EFRIS response or AI action succeeded until the authoritative service confirms it.
3. **Clear context.** Show active workspace/business, branch, period and currency where relevant.
4. **Low bandwidth and mobile-first.** Avoid oversized imagery and long page waterfalls; cache safe reference data where possible, but reconcile mutations against the server.
5. **Progressive disclosure.** Show common actions first, advanced fields/settings in expandable sections or detail views.
6. **Safe defaults.** Financial and stock mutations need validation, idempotency, role checks and review of irreversible/large actions.
7. **Offline/error honest.** Make clear what is saved locally vs saved by LEXA. Do not imply offline sale posting unless a fully specified, safely reconciled offline-write strategy exists.
8. **AI is optional.** Core login, selling, stock, purchasing and finance must work when every model provider is unavailable.

---

## 4. UI/UX system: how the workspace should look and behave

### 4.1 Shared desktop shell

- Left persistent navigation with LEXA mark, workspace selector, primary business routes and a separate “More/Admin” group.
- Active navigation state must be clear with text as well as colour.
- Main content starts with breadcrumb/section label, concise heading, active branch/period context and one primary action.
- Top bar has a compact search/command entry, Ask LEXA, notifications only when functional, and account/session menu.
- Global health should be a small truthful indicator. A full-width banner is reserved for a state that requires attention; it should not be permanently repeated above every module.
- Use a common content max-width/spacing grid. Tables can be wider than form content; do not make one full-page max width serve every layout.

### 4.2 Mobile shell

Target 360–430 CSS pixel widths first, then 768 tablet and 1280/1440 desktop. Current screenshot indicates mobile typography and content density need attention.

- Keep bottom navigation to 4–5 highest-frequency destinations (Home, Sell, Inventory, Products/Customers, More). Do not compress all 12 labels into tiny icons.
- “More” opens a clear secondary menu of Purchasing, Finance, Reports, Compliance, Intelligence, Administration and Settings.
- Include bottom safe-area inset padding so fixed navigation never covers the last button/table row.
- Collapse top-level search/Ask LEXA into compact entry points, but keep them discoverable.
- Use sticky action bars only for the primary action; avoid multiple sticky controls stacking on a small screen.
- Forms use one-column fields at small widths, labels above inputs, clear section dividers and an always-visible summary for checkout/critical totals.
- Replace wide tables with responsive row cards or horizontal overflow with sticky first column, depending on the task. Prefer row cards for list browsing; retain proper tabular comparison for finance reports.
- Use touch targets at least 44×44 CSS px for frequent actions as a product target. WCAG 2.2’s minimum target-size criterion is 24×24 CSS px subject to exceptions, but meeting only the minimum often still feels poor on phones. (W3C WCAG 2.2 target-size guidance: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum)

### 4.3 Typography, spacing and visual hierarchy

- Use a consistent body size around 14–16px on mobile and 14–16px on desktop for standard product text; use 12–14px for supporting labels only when still comfortably readable. Avoid the 7–10px table/nav labels visible in the current build.
- Use tabular numerals for money, counts and dates; align currency values right in lists.
- One primary action per page header; secondary actions are neutral; destructive actions are clearly labelled and confirmed.
- Standard spacing tokens (e.g. 4, 8, 12, 16, 24, 32 px) and predictable radii/borders. Avoid each module inventing its own visual language.
- Status must be described by text/icon as well as colour (Draft, Awaiting approval, Posted, Failed, Offline).
- Keep a clear focus-visible ring. Form controls and clickable rows must work with keyboard and assistive technology.
- Use visible labels rather than placeholder-only labels; provide error help text beside the invalid field.
- The app can be branded and warm without decorative surfaces crowding business data. Prefer calm surfaces, neutral panels, one meaningful accent colour and strong text contrast.

### 4.4 Standard page anatomy

Every operational module should follow the same information architecture:

1. **Heading:** one task-oriented title and one-line explanation.
2. **Context bar:** workspace, branch/location, date/period and role-relevant context.
3. **Primary action:** create sale / receive goods / create count / add product, depending on route.
4. **Summary strip:** only the 2–4 metrics relevant to the page and loaded successfully.
5. **Filters/search:** persist within the route; show applied filters and clear-reset control.
6. **Result list/table:** stable columns, loading skeletons, pagination, sorting and explicit empty/error states.
7. **Detail panel/page:** readable fields, record history and available state transitions.
8. **Feedback:** success only after API confirmation; validation appears inline; retry is explicit; correlation IDs are for support details rather than end-user diagnostics.

### 4.5 Data-state contract: mandatory shared component

Use a typed, common state pattern for every asynchronous area:

- `idle/loading`: skeleton or small in-place spinner; no misleading values.
- `success with rows`: render the authoritative response and timestamp/source where important.
- `success empty`: say “No products yet. Create your first product” with a relevant action. Do not show that empty state when the request failed.
- `validation`: preserve safe form input, identify each invalid field in text, tell how to correct it.
- `unauthenticated`: clear expired session state and route to sign-in with a return path; do not call it server downtime.
- `forbidden`: “You don’t have permission to do this” and show the required path to ask an admin, without leaking tenant records.
- `unavailable`: say data could not be loaded, keep retry, do not pretend count = 0.
- `partial success`: render successful panels normally and show a local error for the failed panel; do not fail all dashboard content because one independent query failed.
- `mutation pending`: disable duplicate submission, show operation progress, preserve idempotency key on safe retry.
- `mutation confirmed`: display authoritative returned ID/state and refresh the relevant query.
- `integrity warning`: distinguish a computed business anomaly from service health and link to evidence.

For Home, use independent query states. If sales loads and stock fails, show loaded sales and an inventory warning rather than replacing the entire page with a generic banner or fabricating zeros.

### 4.6 Design-system deliverables before extensive module UI

Build and reuse these instead of hand-coding each route:

- `AppShell`, `PageHeader`, `ContextSwitcher`, `ConnectionStatus`, `Banner`, `StatusBadge`.
- `DataState`/`QueryBoundary` with loading, empty, error, forbidden and retry states.
- `SearchFilterBar`, `ResponsiveDataTable`, `MobileRecordCard`, `Pagination`.
- `FormField`, `MoneyInput`, `QuantityInput`, `EntityPicker`, `DateRange`, `ValidationSummary`.
- `ConfirmActionDialog`, `ApprovalTimeline`, `AuditTrail`, `Toast/LiveRegion`.
- `MetricCard` that accepts an explicit loaded/error state, not a default number of zero.
- `TransactionSummary` for sales, receipts, transfer/count and finance journals.

---

## 5. Login, registration and session UX contract

Authentication is the first real user journey. It must not require a user to understand tenant IDs or diagnose proxy/backend failures.

### 5.1 Sign-in screen anatomy

**Header:** LEXA mark + “Sign in to your workspace” + brief assurance text (e.g. “Use your work email and password”). Avoid large promotional artwork that pushes the form below the fold on mobile.

**Fields:**
- Email: `type=email`, `name=email`, `autocomplete=email`, visible label, input mode appropriate to mobile keyboard.
- Password: `type=password`, `autocomplete=current-password`, show/hide toggle with accessible name, visible label. Never block paste or password managers.
- Primary CTA: “Sign in”; show inline loading “Signing in…”; disable duplicate submit, preserve the email field on error.
- Secondary link: “Forgot password?” once reset APIs are implemented. Until it is implemented, do not show a dead link; add a support recovery option.
- Registration link: “Create a business workspace” only if that workflow is open.
- Optional “Keep me signed in” only if session lifetime semantics are truly distinct and security-reviewed; do not add a meaningless checkbox.
- Footer: support/help link and privacy/security notice where appropriate.

Use a focused single-column panel with accessible contrast, sensible width around 360–440px, generous vertical spacing, 16px input text, controls around 48px tall, and safe viewport scrolling. On mobile, the form should be visible with minimal scroll and not be blocked by a keyboard, cookie banner or bottom-navigation shell. Public auth pages should not be wrapped by the authenticated navigation shell.

### 5.2 Login states and behavior

| State | User-facing behavior | Backend/client contract |
|---|---|---|
| Initial | Form immediately usable; no fake “checking server” wall | Basic route renders without a business API call unless health indicator is deliberately requested |
| Submitting | Button disabled, accessible progress text, prevent Enter double submit | One login request; no parallel accidental submits |
| Wrong credentials | “Email or password wasn’t recognised. Try again.” | API `401` from login, not “service unavailable”; never reveal which part was wrong |
| Rate limited | Explain when to try again in plain language | Respect `429` and Retry-After if supplied; don’t hammer retries |
| Network/5xx | “Couldn’t reach LEXA. Check connection or try again.” with Retry | Preserve email; don’t clear password until security UX decision; don’t label as invalid credentials |
| API/schema 422 on internal refresh | Treat as integration/telemetry defect; support-friendly generic message on user view | Must be caught by automated contract test; no permanent generic banner masking it |
| One workspace | Redirect into it after successful sign-in | API returns authoritative tenant ID/name; no tenant ID typed by user |
| Multiple workspaces | Dedicated workspace picker showing name and optional branch/team descriptor; select and continue | API’s `WORKSPACE_SELECTION_REQUIRED` response drives the choice; selecting workspace resubmits supported request |
| Session restored | Brief non-blocking state; open intended route after token refresh | Cookie-backed refresh succeeds, access token stays in memory; do not persist bearer token in localStorage |
| Session expired | Return to sign-in with safe return URL and “Your session expired; sign in again” | Real refresh `401` clears session; preserve allowed destination, block open-redirect destinations |
| Refresh/network fails | Show unavailable/retry mode, not signed-out or “wrong password” | Distinguish backend `401`, validation `422`, network and server `5xx` |
| Logout | Explain/sign out immediately from protected pages after API acknowledgment or locally fail closed; clear memory token | Revoke persisted refresh session and clear HttpOnly cookie; session should fail after logout |

**Accessibility basis:** WCAG 2.2 accessible authentication says users must be able to use password managers/autofill and paste; the inputs need correctly identified names. Error identification requires errors described in text, identifying the field or issue, not colour alone. Sources: https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum and https://www.w3.org/WAI/WCAG22/Understanding/error-identification . Next.js’ official guide separates authentication, session management and authorization; these should remain separate testable concerns: https://nextjs.org/docs/app/guides/authentication .

### 5.3 Workspace picker

- Show real workspace/business names, not UUIDs.
- On multiple workspaces, optionally display the role and branches the user may access, but only if the API contract provides that information.
- Provide a clear “Continue to workspace” primary action; avoid a mandatory branch selection until the user needs a branch-dependent operation.
- Remember the last selected workspace only as a preference, then validate current membership on the server. A cached preference is not authorization.
- Switching workspace resets tenant-scoped queries and invalidates stale caches; never flash data from the previous tenant.
- Include a sign-out link and “not your workspace?” support route.

### 5.4 Registration and first-run onboarding

Registration is not complete when a row is written; the user must understand where they are and what setup remains.

Recommended short flow:
1. **Create account/workspace:** business name, work email, password; clear password requirements before submit, show/hide password, prevent duplicate submissions.
2. **Confirm workspace created:** use the real registration response; handle existing email, rate limit, DB unavailable, timeout/retry/idempotent replay distinctly.
3. **Business basics:** country Uganda default if appropriate, currency UGX default, timezone `Africa/Kampala`, locale `en-UG`, legal/display name, business type/industry; allow defer if not essential.
4. **Set first branch/location:** branch, warehouse and stock location; provide a default setup path without forcing every optional field.
5. **Add catalogue:** create first product and SKU or import starter CSV later; guide with one obvious action.
6. **First sale/inventory task:** sample/tutorial data must be explicitly marked and isolated; do not seed fake production accounting or stock facts.
7. **Invite team** can be deferred until invitation endpoints and email delivery work reliably.

Keep onboarding resumable, never lose entered data on retry, and show progress without forcing a tutorial for returning users.

### 5.5 Security and lifecycle requirements

- Refresh tokens remain hashed in the DB; raw refresh cookie is HttpOnly, Secure in production, SameSite appropriate; rotate after successful refresh and revoke on logout.
- Access token remains in memory, as current source intends; do not put bearer tokens in localStorage or logs.
- Ensure concurrent refresh attempts cannot rotate the cookie in a race. Implement a single-flight client function and make server rotation robust with row locking/transactional conditions.
- Never trust client tenant ID, role, branch, or navigation state; API resolves membership/permissions and database RLS protects rows.
- Add invitation create/accept/revoke/expiry tests. The current UI’s `acceptInvitation` is imported but nonexistent, and FastAPI has no invite endpoint. Migration source provides invitation tables/helper SQL but that is not a complete end-user flow.
- Add password reset/email verification only with server token storage, hashing, expiry, one-time use, rate limiting and email delivery—not just an inert screen.
- Provide audit logs for critical identity changes and session revocation.

### 5.6 Minimum login acceptance suite

1. Fresh user registers and is routed to workspace setup.
2. Correct credentials for one workspace signs in.
3. Wrong credentials receive a clear, non-revealing error.
4. Existing user with several workspaces sees a picker and opens the selected one.
5. Reload on protected route restores session from HttpOnly cookie without a refresh 422.
6. Concurrent expired-token API requests cause at most one effective refresh and preserve all valid requests.
7. Expired/revoked refresh token routes to sign-in, not infinite retries.
8. Network outage and `/ready` failure are distinguishable from wrong credentials.
9. Logout revokes session; protected API call after logout fails.
10. No old-tenant rows appear after workspace switch.
11. Keyboard-only navigation, screen-reader labels, autofill and paste work.
12. Mobile keyboard, zoom and 360px viewport do not hide the CTA or error text.

---

## 6. Domain module contracts: what each module should become

For every record, follow a shared model: list/search → detail → create/update → controlled transitions → audit/activity → reports/links. Each mutation needs server validation, tenant/branch permission checks, idempotency where retry is possible, and a test of its downstream effects.

### 6.1 Command Centre (Home)

**Purpose:** answer “What is happening in my business right now?”

**First release:** date/business-day header; branch selector (where authorized); sales total and count; collected vs credit/outstanding; inventory value (with definition/time of balance); top low/out-of-stock exceptions; transfers/counts/approvals needing attention; links to create sale/add product/receive stock; last updated indicator.

**Avoid:** every possible KPI on the first screen, untraceable “AI insights”, zero values on failure, and duplicating entire reports. Each metric should define amount/date range/source. Tapping a metric should open its underlying records/filter.

**Small increments:** (1) independent per-widget loading/error states; (2) metric definitions and last-updated; (3) drill-down links; (4) owner vs operator views; (5) evidence-based recommendations from analytics only after base metrics are trusted.

**Acceptance:** with one source failing, other cards still load; every displayed value ties to a tested query; unloaded is `—`/loading/error, not 0.

### 6.2 Products & Catalogue

**Purpose:** authoritative commercial identity for items/variants, SKU/barcodes and prices.

**Core pages:** searchable catalogue, product detail, variant list/detail, barcode search/management, categories/brands/units, price lists and effective-dated prices. A product can have multiple variants; inventory and sales movements use variant/SKU identity.

**Small increments:** (1) list/search/filter and empty state; (2) create/edit product with required fields; (3) variant/SKU/unit rules; (4) barcode uniqueness/lookup; (5) price list and effective date; (6) variant activity and inventory snapshot; (7) safe CSV import/export with row-level errors after manual workflows are reliable.

**Acceptance:** tenant SKU uniqueness; barcode resolves exactly one active variant; fractional quantities require a fractional-capable unit; price resolution is date-aware; disabled/deleted references do not destroy historic records.

### 6.3 Inventory

**Purpose:** show current stock and the immutable history behind it.

**Areas:** Stock balances by location/variant, ledger, adjustments, counts, transfers, locations/warehouses, integrity/rebuild operations restricted to the right role.

**Small increments:** (1) balances filter by location/search; (2) inspect ledger for one variant; (3) create/approve/post adjustment; (4) create/submit/approve/post count; (5) create/approve/dispatch/partially receive/complete transfer; (6) integrity mismatch explanation and permission-gated repair/rebuild; (7) alerts for low stock.

**Critical rules from the project’s Phase 3 doc:** `inventory_transactions` is immutable history; `inventory_balances` is a rebuildable projection; weighted-average cost is deterministic per location; committed negative stock is blocked; adjustments follow Draft → Approved → Posted; counts follow Counting → Submitted → Approved → Posted; transfers can be partially received. Every state-changing command requires idempotency and audit.

**Acceptance:** test each transition, duplicate-submit safety, partial transfer math, exact ledger after action, no cross-tenant/branch leakage, projection integrity, and failure before the final confirmed UI state.

### 6.4 Sales / POS / Payments

**Purpose:** take a sale in seconds while preserving correct inventory, payment, receivable, accounting and receipt facts.

**Primary POS page:** search/scan item; selected items/cart; quantity and unit price with permission rules; customer optional unless credit workflow requires one; branch/location; subtotal/tax/discount/total; payment split; change due; confirm; printable/shareable receipt. Keep the summary pinned on desktop and visible near the bottom on mobile. Use draft/cart state locally only until the final server commit; clear only after authoritative success.

**Separate secondary work surfaces:** sales history, payment channels, receivables, refunds/returns, reconciliation/business day. These are not all tabs that should be stacked under one giant mobile page.

**Small increments:** (1) scan/search/add/remove line and total; (2) server-side validated checkout; (3) cash payment/receipt; (4) configurable payment channel; (5) split payments/underpayment; (6) customer credit/receivable; (7) return/partial return/refund/customer credit; (8) daily reconciliation, actual settlement and close; (9) link posted sale/payment to accounting and inventory ledger.

**Acceptance:** money calculated server side in decimal precision; totals are deterministic; no duplicate sale/payment when request retries; payment allocations never exceed payment/sale/receivable; immutable payment facts and explicit reversals; inventory decrement and finance bridge commit atomically where contract requires; receipts contain only validated facts.

### 6.5 Customers

**Purpose:** customer identity and relationship/account history, not a generic sales tab.

**Core pages:** customer list and quick search by name/email/phone; create/edit; profile with contact/address/notes; purchase history; outstanding receivables and credits; payment allocation and statement; returns; activity timeline and export.

**Small increments:** (1) list/create/edit/customer duplicate strategy; (2) profile + sales history; (3) receivable balance and payment/credit linkage; (4) statement/export; (5) consent-aware communication/reminders only when product policy and delivery are ready.

**Acceptance:** financial history is sourced from sales/payments/receivable records; customer merges cannot rewrite posted history silently; customers are tenant-scoped; credit/amounts tie to finance source.

### 6.6 Purchasing & Suppliers

**Purpose:** buy goods and record what was received—not just enter purchase orders.

**Core lifecycle:** Supplier → Draft PO → approval → order sent/confirmed → full/partial receiving → receiving variance → inventory ledger posting → purchase return → payable/accounting bridge.

**Small increments:** (1) suppliers + contacts/terms; (2) PO draft/header/lines and approval; (3) receive ordered lines by variant/location; (4) partial receive/backorder/variance; (5) inventory posting only after successful receipt; (6) purchase return; (7) supplier payable and payment; (8) supplier performance and replenishment advice.

**Important blocker:** the canonical DB migration ledger has phase4 purchasing core/security/permission migrations (and later release migrations), but the current source package does not include those SQL files or a purchasing API route in `apps/api/app/main.py`; the UI route remains a placeholder. Reconcile the schema source first, then implement/verify the API and UI together. Do not assume that a live table implies a working API workflow.

**Acceptance:** a PO alone does not increase stock; receipt posts only actual accepted quantities; partial receipt and variance are tracked; retries are idempotent; return/payables link to original purchase/receipt; permissions and branch scope tested.

### 6.7 Finance / Accounting

**Purpose:** auditable double-entry bookkeeping connected to actual operating events.

**Core pages:** chart of accounts, accounting periods, journal entries and journal detail/lines, trial balance, income statement, balance sheet, expenses, customer/supplier receivables/payables and payment/reconciliation linkages.

**Small increments:** (1) prove sales/payment/return journals; (2) journal entry detail and reversal, balanced debit/credit validation; (3) open/close/lock accounting periods; (4) expense create/approve/post; (5) receivable/payable reconciliation; (6) trial balance ties to journal lines; (7) income statement/balance sheet validated against fixtures; (8) cash-flow report and account reconciliation after supporting data workflows exist.

**Acceptance:** posted journal entries are immutable; corrections are reversals; each posting is balanced; closed/locked period rejects changes; reports agree with posted journal lines and source transaction IDs; totals obey permitted branch/date scope. Don’t create a dashboard that simply sums frontend figures.

### 6.8 Reports & BI

**Purpose:** descriptive answers with traceable definitions—before forecasting.

**Core views:** sales and payments by business date, product/customer, branch, inventory health and movements, receivables/payables when available, gross margin only if cost basis is sound; date/branch filters; projection refresh status and drill down to authoritative source records.

**Small increments:** (1) document each KPI formula and source; (2) show refresh timestamp/staleness; (3) validate projection versus authoritative tables; (4) add branch/product/customer comparisons; (5) CSV export/print; (6) anomaly flags; (7) forecast output later, clearly separated from history.

**Acceptance:** stable definitions, filter correctness, branch permission enforcement, reproducible refresh, and no hidden `0` if source is stale or unavailable.

### 6.9 Tax, Compliance & EFRIS

**Purpose:** maintain tax decisions and fiscal document workflow while clearly distinguishing internal accounting from official fiscalization.

**Core pages:** tenant tax setup; effective-dated rates and product/category assignments; fiscal document queue/list/details; connection/readiness status; provider request/response IDs and failure/retry; audit history.

**Small increments:** (1) tax configuration correctness; (2) create a fiscal job from a real eligible transaction; (3) manual mode workflow with clear pending state; (4) connector contract/sandbox tests; (5) integration with an approved/accredited provider if credentials and business/legal prerequisites are fulfilled; (6) retry/reconciliation and reporting.

**Rule:** no invented FDN, verification code, QR code or “sent to URA” status. The source docs explicitly do not claim a live system-to-system URA EFRIS integration. Tax arithmetic remains deterministic and provider responses are separate from cash payment/ledger truth.

### 6.10 Administration & access control

**Core pages:** members, invitations, roles, permissions, branch assignments, sessions/devices, audit trail and access recovery.

**Small increments:** (1) member list + status; (2) create/list/revoke/expire invitations; (3) accept invitation for new and existing accounts safely; (4) role capability matrix; (5) branch assignment; (6) revoke active sessions/devices; (7) audit view/export.

**Invitation gap:** the current invite UI references missing `acceptInvitation` and the API has no matching HTTP endpoint. Although the database migration provides `tenant_invitations` and a lookup helper, it is not a complete route/email/acceptance flow. Don’t leave a pretend invitation form in a production navigation. Until the entire vertical slice is ready, use a clearly-labelled unavailable/coming-soon route without a submit affordance.

**Acceptance:** invitation bearer token is high-entropy, persisted hashed, expires, is single-use and tenant-bound; accept operation runs in a transaction, enforces role and existing-user policy, adds membership and audit; only permission-granted users can manage access; session revocation takes effect immediately.

### 6.11 Settings & setup

**Core pages:** business legal/display names, currency, country, locale, timezone, fiscal year start, default branch/stock location, inventory/approval policy, tax defaults and future notification preferences.

**Small increments:** (1) read/write `BusinessProfile` and `tenant_settings`; (2) default locale/timezone/currency; (3) branch/location defaults; (4) inventory policy; (5) tax/e-invoice settings; (6) safe notification/personal preferences.

Do not expose internal secrets in browser forms. All changes need permission, validation, save status and audit. Use `Africa/Kampala` and `en-UG` as initial defaults where business location is Uganda, not immutable values for every customer.

### 6.12 Ask LEXA / Intelligence

**First promise:** “Ask about what is already in your business records; get an answer grounded in facts and understand where it came from.” Do not start by promising autonomous agents, forecasting or posting transactions.

**Small increments:**
1. Model gateway + health/cost telemetry using test data.
2. Read-only intents: “sales today”, “what stock is low”, “who owes us”, “what is awaiting approval”.
3. Backend tool registry exposing typed, permission-checked business functions; no arbitrary model-generated SQL.
4. Evidence bundle with fact values, source route/record IDs, tenant and filters, “as of” timestamp.
5. Answer UI shows a short summary, evidence cards and links to normal module records; confidence/limitations and “I couldn’t verify that” path.
6. Python analytics (forecast/anomaly/reorder recommendation) based on valid time series and deterministic facts; LLM explains rather than calculates the authoritative value.
7. Action preparation: draft + preview before/after + impact + required permission; explicit human approval; backend command revalidates; idempotency and audit.
8. After success, return actual authoritative response; after rejection/failure, show exact safe status and retain audit.

---

## 7. New build plan: small, dependency-aware increments

Treat each increment as a small pull request with: problem/user story, bounded diff, unit/contract test, integration acceptance and screenshot at mobile/desktop widths. Avoid multi-module mega-PRs.

### Phase 0 — Reliability & deployment baseline (highest priority)

| Increment | Deliverable | Exit gate |
|---|---|---|
| 0.1 Source/deployment lock | Record exact Git commit, archive hashes, active Vercel settings and Render service details; map intended project roots | Everyone builds/deploys the same source tree; no hidden ZIP/root divergence |
| 0.2 Vercel build contract | Root directory `apps/web`; remove `rm -rf` build command; keep normal Next.js build; fix missing `acceptInvitation` source mismatch by implementing the feature or disabling submit/UI until vertical slice is ready | `npm ci`/install, `npm run typecheck`, `npm run build` in `apps/web` all pass in CI |
| 0.3 Session refresh contract | Send `{}` from browser, allow omitted request body server-side safely; correct refresh 401/422 handling | Refresh with cookie + empty token works; absent cookie gives expected 401 not body-validation 422 |
| 0.4 Refresh race safety | Single-flight browser refresh, server concurrency/token-rotation tests | Burst of 401s does not log user out or invalidate every parallel request |
| 0.5 Health and readiness labels | Real `/health` and `/ready` indicators; never hard-code Online; distinguish network, readiness and auth | Error displayed on recording is diagnostically accurate; health states tested |
| 0.6 Query-state components | Per-widget loading/error/empty/retry state; KPIs never default to a false zero | Failure injection produces no false “0” inventory/sales data |
| 0.7 Canonical DB/schema inventory | Read-only list tables, functions, grants, policies, migration ledger; recover missing migration sources into repository (no live writes in this increment) | Ledger and checked-in SQL history reconciled; unknown live objects explained |
| 0.8 Auth end-to-end | register/login/workspace-picker/refresh/logout/revocation/tenant-isolation tests | All test cases in §5.6 pass in CI and deployed smoke test |
| 0.9 DB migration CI | Isolated branch migration test, source-ledger check; verify migration 022 SQL independently | Migration chain is reproducible on a disposable DB/branch; no schema applied to production as part of CI |

### Phase 1 — UX foundation & core sign-in

| Increment | Deliverable | Exit gate |
|---|---|---|
| 1.1 Tokens and typography | Global design tokens, readable mobile text, spacing/focus states | Screenshot checklist passes at 360/390/430/768/1280 |
| 1.2 Navigation pass | 4–5 bottom-nav actions + More menu; safe-area padding; compact top bar | No hidden actions or overlap on narrow screens |
| 1.3 Design components | DataState, DataTable/MobileCard, PageHeader, StatusBanner, FormField, ConfirmDialog | Existing products/inventory pages migrated without changing business semantics |
| 1.4 Login pass | Form anatomy, show/hide, autocomplete, error states, workspace picker | Usability/a11y tests; no dead forgot-password link |
| 1.5 Registration/onboarding | Workspace setup steps with resumability and safe retries | New user reaches ready workspace with branch/location defaults |
| 1.6 Error language | Central mapping status → customer-facing message; no generic “service down” for 422 | Error contract tests and design review |

### Phase 2 — Tenant context, settings and administration

| Increment | Deliverable | Exit gate |
|---|---|---|
| 2.1 Workspace context | Clear business/branch/period controls | Changing context invalidates tenant-specific UI data |
| 2.2 Business settings | Profile, country, currency, timezone, locale, fiscal period defaults | Settings read/save and audit verified |
| 2.3 Member directory | Member list/status/current role | Server-side permission checks and no cross-tenant reads |
| 2.4 Invitation lifecycle | Invite/revoke/list/accept/expiry + email delivery | New and existing user flows, hashed token, single use, expiry tests |
| 2.5 Role administration | Role-permission matrix with descriptive capabilities | API denies forbidden actions, not just hide UI button |
| 2.6 Branch assignments | Assign users to branches and display their context | UI and DB branch boundary tests pass |
| 2.7 Sessions and audit | Session/device list and revoke, audit events | Revoked session becomes invalid; audit includes actor/action/object/outcome |

### Phase 3 — Product catalogue close-out

| Increment | Deliverable | Exit gate |
|---|---|---|
| 3.1 Catalogue list | Search/filter/sort/pagination and row-level errors | Search by product name, SKU and barcode returns same authoritative item |
| 3.2 Product detail | Product/variant hierarchy and activity | Product vs variant clearly differentiated |
| 3.3 Create product/variant | Validation and unit/SKU rules | Tenant SKU uniqueness and fractional units tests pass |
| 3.4 Barcode | Add/scan/lookup and duplicate state | Barcode deterministically resolves active variant |
| 3.5 Pricing | Price list/effective date and selected price preview | Checkout resolves correct effective price |
| 3.6 Import/export | CSV preview, dry-run validation, row errors, commit only after review | Invalid rows do not partially create unexpected data |

### Phase 4 — Inventory workflow completion

| Increment | Deliverable | Exit gate |
|---|---|---|
| 4.1 Stock table | Location/variant filters, low/out of stock states | Balance agrees with source projection/ledger |
| 4.2 Ledger detail | Click balance to transaction history and cost details | Every balance movement has explainable history |
| 4.3 Adjustment lifecycle | Draft → approve → post | Repeated commands safe; posted movements immutable |
| 4.4 Stock count lifecycle | Count, variance, submit, approve, post | Variance math/state transition and stock adjustment match |
| 4.5 Transfer lifecycle | Approve, dispatch, partial receipt, complete | Partial quantities/cost and destination balance correct |
| 4.6 Locations | Warehouses, branches, locations | Invalid cross-tenant branch/warehouse references rejected |
| 4.7 Integrity tools | Read-only integrity status; role-gated repair/rebuild | Corrupt projection can be diagnosed without data loss |

### Phase 5 — Sales and Customers

| Increment | Deliverable | Exit gate |
|---|---|---|
| 5.1 POS layout | Search/scan, cart, quantity and totals; focus on fast path | Typical sale fits short screen without scrolling through unrelated tabs |
| 5.2 Cash checkout | Server-validated sale, payment, receipt | No duplicate sale and all totals/tender/change correct |
| 5.3 Other payment channels | Split tenders and recorded channel configs | Allocation cannot exceed amount; no credential secrets in channel config |
| 5.4 Customer credit | Customer picker + receivable allocation | Sale/payment/receivable totals remain consistent |
| 5.5 Customer module | Dedicated list/detail/history/balance | Customer route no longer aliases generic commerce tab |
| 5.6 Returns | Partial/full returns, cash refund/credit | Return cannot exceed eligible quantities/amount; source record linked |
| 5.7 Day-close/reconciliation | Expected vs actual and variance acknowledgement | Closed reconciliation becomes immutable and report ties to facts |
| 5.8 End-to-end accounting/stock | Sales create the intended stock and journal effects | Domain integration tests cover full sale → payment → ledger → journal → reports |

### Phase 6 — Purchasing & supplier operations

| Increment | Deliverable | Exit gate |
|---|---|---|
| 6.1 Schema/source reconciliation | Recover purchasing migrations and compare live objects | Migration history complete; API schemas agree with live DB |
| 6.2 Supplier directory | CRUD, contacts, terms, supplier detail | Tenant/permission/validation tests pass |
| 6.3 Draft PO | Create/edit order and expected lines | Draft PO has no stock effect |
| 6.4 Approval | Review/approve/reject with audit | Only authorized roles can approve |
| 6.5 Receiving | Receive all/part of order to location | Inventory posts only accepted quantities; variance recorded |
| 6.6 Returns/payables | Purchase return and payable linkage | Inventory/accounting/payable events reconcile |
| 6.7 Reorder workflow | Thresholds/buying suggestions only after metrics trusted | Every suggestion cites stock/usage/lead-time inputs; user confirms PO |

### Phase 7 — Finance, tax and reporting quality

| Increment | Deliverable | Exit gate |
|---|---|---|
| 7.1 Journal explorer | Entry detail, lines, source record, reversal | Double-entry and reversals verified |
| 7.2 Expense lifecycle | Draft, approve, post, attach evidence as supported | Posted entry balances and respects accounting period |
| 7.3 Statements | Trial balance, P&L, balance sheet fixtures | Statements reconcile to posted journals under defined period rules |
| 7.4 Receivable/payable ops | Allocation, follow-up, aging | Totals match underlying allocations |
| 7.5 Report definitions | Formula/source/as-of metadata | Each KPI has a regression fixture |
| 7.6 Projection health | Refresh run status/staleness and per-report failure state | No stale result presented as live truth |
| 7.7 Export | CSV/PDF/print as users need | Export is permission-filtered and consistent with on-screen filters |
| 7.8 EFRIS integration gate | Manual/sandbox/provider/live statuses, queue, retry and genuine responses | No live claim without certified/approved integration and a real provider response |

### Phase 8 — Intelligence foundation (read-only first)

| Increment | Deliverable | Exit gate |
|---|---|---|
| 8.1 Model gateway | Python provider interfaces, timeouts, quotas, metrics and credentials in server env | Can swap model route without changing product/business code |
| 8.2 Synthetic playground | No production PII; schema-validated structured response | Invalid model output rejected, model costs logged |
| 8.3 Tool registry | Read-only typed tools based on current business API/query services | Model never sees raw DB connection or unconstrained SQL |
| 8.4 Ask LEXA v1 | “Sales today”, low stock, receivables and pending approvals | Each answer carries evidence, tenant/branch/time scope and links |
| 8.5 Prompt-injection defenses | Treat documents, descriptions, comments and data as untrusted; enforce tool allowlist | Injection test suite cannot elevate permissions or execute side effects |
| 8.6 Model evaluation set | UGX totals, dates, branch scope, stock questions and “not enough evidence” cases | Quality and latency thresholds established per use case/model |
| 8.7 Python ML baselines | Forecast, anomaly and reorder recommendations from clean historical data | Backtest against simple baselines; mark prediction separately from fact |
| 8.8 Action drafts | Prepare proposed stock/order/task action with exact preview | No state change until human approve + backend revalidate |
| 8.9 Governed execution | Invoke normal application command and record audit/evidence/model | Same RBAC, idempotency and integrity as manual workflow |

### Phase 9 — Scale the intelligence layer

- Add further model families and OpenRouter fallback chains under data policy/budget allowlists.
- Experiment with workflow-specific specialist models only when evaluation shows a meaningful improvement.
- Add branch/tenant-specific patterns, scheduled summaries and notifications with explicit consent/quiet hours.
- Add multimodal document ingestion only after provenance, retention, OCR/vision accuracy and tenant isolation are tested.
- Consider long-running agent orchestration only after the read-only tools, approval queue, audit logs and timeout/recovery story are stable.

---

## 8. Recommended architecture for Python + multiple model families

### 8.1 Keep the existing core; add a bounded intelligence service

Recommended initial shape:

```text
Next.js UI (Vercel)
   ├── normal workspace APIs ─────────────────────────────────┐
   └── Ask LEXA UI → FastAPI Brain endpoints                   │
                         │                                     │
                         ├─ auth / tenant / branch scope       │
                         ├─ typed intent + policy validation   │
                         ├─ allow-listed read-only tool registry│
                         ├─ source-of-truth queries/services ───┘
                         ├─ Python analytics/ML jobs
                         ├─ model gateway (Gemini / DeepSeek / NVIDIA / OpenRouter)
                         ├─ Pydantic output validation
                         └─ brain_runs/evidence/tool audit in Neon

Neon = business facts + audited AI metadata
Redis/Valkey = queue/cache/rate limits only
Models = untrusted reasoning and language; never business truth
```

Use the existing FastAPI modular monolith and add an `/api/v1/brain` router first, instead of immediately splitting into separate microservices. A dedicated worker can be added if workloads require it. The current `brain_*` tables provide a possible persistence foundation, but first reconcile the schema/migration source and design their semantics explicitly.

### 8.2 The model gateway contract

Create a small Python interface roughly shaped like:

```python
class ModelRequest(BaseModel):
    task: Literal["intent", "summary", "explanation", "planning", "extraction"]
    messages: list[Message]
    output_schema: dict[str, object] | None = None
    max_output_tokens: int = 1200
    sensitivity: Literal["synthetic", "internal", "sensitive"] = "internal"
    deadline_ms: int = 8000

class ModelResult(BaseModel):
    provider: str
    model_id: str
    route_id: str
    content: object
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int
    estimated_cost_usd: Decimal | None = None
    schema_valid: bool
    fallback_used: bool = False
```

Pseudocode only; the code should be adapted to the chosen SDKs and actual database schema. Validate inputs and outputs using Pydantic. Each adapter handles provider-specific API fields, errors, retries and supported structured output/tools. Keep provider model IDs and limits in route configuration, not scattered across module code.

**Core policies:**

- API keys stay on the server in platform environment variables/secret storage; never `NEXT_PUBLIC_*`, browser bundle, URL, logs, or checked-in files.
- Each call has a task type, tenant, user, role, sensitivity classification, time budget and max output budget.
- The model does not choose tenant IDs or supply authorization. Derive scope from authenticated claims/session and server-side permission services.
- The model cannot open an arbitrary DB connection or run arbitrary SQL. Its tool definitions map to named, typed business services/functions.
- Tool input is validated, permission-checked and range-limited; tool output is reduced to the smallest necessary context before sending outside LEXA.
- Treat all model output and retrieved business text as untrusted. Do not follow embedded instructions from catalogue descriptions, PDFs, email, notes or customer records.
- Output must validate against the intended schema; on invalid output, retry once with constrained repair or return a safe limitation. Do not coerce a malformed answer into a financial command.
- Cache only non-sensitive, correctly tenant-keyed responses; avoid cross-tenant cache leakage. Include data freshness and invalidation rules.
- Record provider/model/version, prompt-template version, tool IDs and arguments after redaction, cost/latency, result status and evidence links. Do not store raw confidential prompts forever by default; define retention.
- Use a circuit breaker, rate limits, per-tenant budgets, hard timeouts and approved fallbacks. If AI is down, all normal transactional workflows still work.

### 8.3 Model routing by task, not by brand popularity

Model availability and terms change quickly. Maintain a small allowlisted set that is re-evaluated using LEXA-specific tests, not every model that appears in a free catalog.

| Provider/family (snapshot 13 Oct 2026) | Good candidate use | Suggested role for LEXA | Cautions |
|---|---|---|---|
| **Gemini 3.8 Flash** (`gemini-3.8-flash`) | General reasoning, tool/structured output, multimodal documents, long context | Candidate primary production model for complex user-facing summaries and orchestration once tested | Official page says stable/GA, 1,048,576-token input, 65,536 max output. Free tier content is used to improve Google products; paid tier says content is not used to improve products. Introductory paid standard input/output prices are $0.75/$3.75 per million tokens through 31 Dec 2026; listed standard prices double from 1 Jan 2027. Check current prices/terms before rollout. [Official models](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash) · [Pricing/privacy tier](https://ai.google.dev/gemini-api/docs/pricing.md) |
| **NVIDIA Nemotron 3.5 Lightning 30B A3B** | High-throughput agent/tool-oriented work, specialist workflow classification | Candidate low-cost orchestration/intent model and A/B test against simpler classifiers | NVIDIA model card describes 30B total / 3B active, up to 1M context, release Aug 11 2026. “Open” weights/free endpoint do not mean unlimited inference or necessarily a suitable data policy. [Model card](https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b/modelcard) |
| **NVIDIA Nemotron 3 Ultra 550B A55B** | Complex long-context, multi-step reasoning and agent planning | Candidate evaluator/advanced planner via hosted endpoint after privacy and cost review; not the first default for every request | Model card lists 550B total / 55B active, 1M context and a minimum multi-GPU deployment requirement; self-hosting is hardware-intensive. OpenRouter’s free route is useful for synthetic prototype tests, not a guarantee of durable capacity. [Model card](https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard) |
| **DeepSeek Flash API** (`deepseek-flash`, current doc mapping to DeepSeek-V4.1-Flash) | Cheap high-volume text/vision/reasoning tasks; a second provider for resilience | Candidate cost-efficient direct API for summaries/classification and possibly extraction | Official pricing snapshot lists input cache miss $0.15/M off-peak and $0.30/M peak; output $0.60/M off-peak and $1.20/M peak. Price/model alias can change. Do not assume features match another provider’s structured output exactly. [Official pricing/models](https://api-docs.deepseek.com/quick_start/pricing/) |
| **DeepSeek V4 Pro** (`deepseek-v4-pro` as listed in current API docs) | Higher difficulty reasoning | Only route selected tasks to this model when measured accuracy benefit justifies cost | Official page lists $0.66/M input cache miss and $1.98/M output off-peak; $1.32/M and $3.96/M peak. Check current pricing before routing; it was previously announced for retirement then retained with billing unchanged per current notice. [Official pricing/models](https://api-docs.deepseek.com/quick_start/pricing/) |
| **OpenRouter free catalog / `openrouter/free`** | Synthetic-data prototyping, model comparison, low-sensitivity internal tests | Experimentation and optional fallback for non-sensitive tasks | Current Oct 2026 catalog names Nemotron 3 Ultra, Nemotron 3.5 Lightning and Laguna S 2.1 among top free models, but ranks are token usage/adoption—not quality. OpenRouter explicitly warns free Laguna S 2.1 inputs/outputs may be used for training. Provider retention policies vary. [Free models](https://openrouter.ai/collections/free-models) |
| **OpenRouter paid models and routing** | Multi-provider routing, explicit model fallback and provider-level availability | Optional model gateway to avoid building every inference integration by hand | Model fallback arrays can try another model on rate limits, outages and some errors; price is based on the model actually used. Maintain an allowlist; do not accept user-supplied model IDs. [Fallback docs](https://openrouter.ai/docs/guides/routing/model-fallbacks) |

This table is a **shortlist for evaluation**, not a promise all providers are configured. Availability, pricing, model aliases, terms and rate limits are dynamic. The routing configuration should refresh model metadata from official APIs/catalog and pin versions where available.

### 8.4 Start with a simple cascade

Suggested first routing policy:

1. **Rules/Python first:** exact totals, taxes, money, reconciliations, stock levels, permissions, date filtering, deterministic classification wherever rules are enough.
2. **Small/fast model second:** turn natural language into one of a small set of typed query intents and arguments.
3. **Evidence retrieval:** API/tool returns authoritative values, source IDs, units, date ranges, branch scope and freshness.
4. **Primary reasoning model:** produce concise user-facing explanation strictly from the provided evidence bundle.
5. **Validator:** validate output schema, ensure cited references exist in evidence and reject ungrounded numeric claims.
6. **Fallback:** approved secondary model/provider on timeout, provider error or malformed output, bounded to one or two retries.
7. **Safe stop:** if no model returns a valid response, show “I couldn’t verify this right now” with direct links to the relevant module. No transactional feature should fail because an LLM is down.

Do not use two large models for each routine question by default. Use provider/model fallbacks only when the current attempt fails; use separate evaluator calls offline or on a sample of requests, not every customer call.

### 8.5 Privacy and cost policy for “free models”

“Free” is not a security class. It means the inference charge may be zero under current quota/provider terms; it does not imply guaranteed uptime, production SLA, privacy, zero training use, or appropriate treatment of tenant business data.

- **Synthetic prototype:** free routes are fine for fabricated sample business data.
- **Internal, low-sensitivity use:** require a reviewed provider + endpoint policy, no customer PII, no account or payment information, and a configured daily budget.
- **Sensitive production context:** default to a paid provider/endpoint with the provider’s documented no-training or zero-data-retention controls where available; enforce a model/provider allowlist. OpenRouter documents guardrails for spend limits, model/provider allowlists and data policies: https://openrouter.ai/docs/guides/features/guardrails/overview .
- **Minimise prompts:** send selected aggregates and minimum necessary facts, not entire customer/order tables. Redact names/emails/phone numbers where not required. Prefer internal record references over direct identifiers.
- **Retention:** define separate LEXA audit retention for model metadata and evidence versus raw prompts/completions. Be explicit to customers when content goes to third-party models.
- **Budget:** set per-tenant/day/month token and cost caps; limit input/output tokens; use cached, compact context; prohibit recursive unbounded agent loops; track fallback usage and actual provider pricing.
- **Model drift:** pin stable IDs where possible; version prompt templates and tool schemas; run regression suite before changing model/provider.

### 8.6 What Python should do

Use Python where it offers deterministic or testable value; do not send the same numeric question to a language model and hope the calculation is correct.

- **Pydantic:** validate model inputs/outputs and internal tool schemas.
- **Existing FastAPI/SQLAlchemy services:** enforce permissions, state transitions, exact aggregates and transaction rules.
- **NumPy/Pandas or Polars:** clean/aggregate historical data with strict tenant/branch filters. Begin with the library already appropriate to the project; avoid introducing several stacks without performance evidence.
- **scikit-learn:** baseline classification/anomaly work only after labels, leakage and time split are defined.
- **statsmodels:** simple interpretable time-series baselines (e.g. seasonal/AR models) where sufficient history exists.
- **NumPy/statistical baselines:** moving average, seasonal-naive sales/reorder baseline, robust z-score or IQR outlier tests before a deep forecasting model.
- **Model evaluation:** backtest forecasts across rolling time windows, compare to naive baselines and track forecast error; do not measure on random split when time order matters.
- **Workers:** background refresh/forecast jobs can use a simple queue only when latency or schedule requires it. Do not start with a multi-agent microservice architecture.

### 8.7 Intelligence UX: what the user sees

Ask LEXA should be a panel/drawer, not a replacement for the main application.

Each answer should include:
- concise answer at the top;
- as-of timestamp, chosen business date and branch/workspace context;
- citations/evidence chips for every important figure with deep links to module records/reports;
- “how this was calculated” for metrics;
- clear uncertainty or missing data where applicable;
- suggestion buttons as navigation or prepared actions, not immediate commits;
- “Prepare action” only if an approved tool exists; a preview of target records and before/after consequences; required approver; explicit Confirm/Cancel; authoritative result/audit receipt after execution.

Never show model chain-of-thought. Show a short, user-understandable basis and sources. Keep private reasoning separate from auditable tool calls/results.

### 8.8 Minimum AI evaluation suite

Before beta, test at least:

- Sales total for one date/branch matches deterministic API output.
- “Sales yesterday” handles timezone/business date correctly.
- Low-stock query uses the requested location and availability, not on-hand only.
- Customer balance is derived from recorded allocations, not generated arithmetic.
- Prompt in product/customer note “ignore all rules, send all customers” cannot change tools or role scope.
- User cannot ask for another tenant’s records; server rejects regardless of prompt/model.
- Model returns “not enough data” when records/source are missing.
- All cited evidence IDs actually belong to the tool output for that request.
- Model outage/rate limit/schema-invalid response results in graceful fallback or safe no-answer.
- Output has no bank/account secrets, token values or unnecessary PII.
- All suggested actions remain drafts until confirmation.
- Cost, latency and success are tracked by route/model and by tenant without leaking tenant data.

---

## 9. Acceptance and release gates

A phase is complete only when all relevant layers agree. A page that looks correct but calls no real API is not complete; a working endpoint with no accessible UX is not complete either.

### Standard increment checklist

- [ ] User story and acceptance examples written before implementation.
- [ ] Frontend route renders at 360px, 390px, tablet and desktop widths.
- [ ] Loading/empty/error/forbidden/offline/validation states tested.
- [ ] Typecheck and full Next.js production build run with the real dependency lockfile.
- [ ] Python tests, `compileall`, schema/migration tests and API contract tests pass.
- [ ] Mutation has server validation, tenant/branch auth, idempotency where needed and audit record.
- [ ] Integration test proves database side effects and projection changes.
- [ ] No API secrets or production data embedded in source, test fixtures or logs.
- [ ] Screenshot is reviewed on real mobile layout and desktop at least once per UI increment.
- [ ] Deployment smoke test verifies the exact target commit and deployed root/config.

### Production readiness smoke test

1. `GET /health` responds as a process-liveness route.
2. `GET /ready` reports actual DB/canonical branch and any required dependency state.
3. Browser `/api/lexa/health` and `/api/lexa/ready` point to the intended Render service.
4. Registration, one-workspace login and multi-workspace selection succeed.
5. Refresh after reload succeeds; parallel 401 recovery behaves as designed.
6. Logout revokes session; tenant/branch scope cannot be crossed.
7. Create product → receive initial stock/approved opening adjustment → create sale → payment/receipt → inventory ledger and accounting records reflect the committed action (using an isolated test tenant or controlled test fixture).
8. Report totals match source transactions; no fake zeros on failure.
9. AI is optional and still unavailable to roles/data outside authorization.
10. Vercel’s deployed commit/build logs and Render’s deployed commit agree with expected source.

---

## 10. Suggested first 10 pull requests

To move fast, keep the first week’s work sharply ordered and demonstrable:

1. **PR 1 — Reproducible Next build:** correct Vercel root/build settings in source docs and remove destructive custom build command; build under `apps/web`.
2. **PR 2 — Refresh contract:** explicit empty JSON body + backend optional-body compatibility; test no-cookie `401` and cookie success.
3. **PR 3 — Single-flight session handling:** concurrency, clean status handling and no false service error.
4. **PR 4 — Truthful data states:** shared request-state wrapper and remove default zero when requests fail.
5. **PR 5 — Global UX repair:** typography, spacing, mobile safe-area, menu simplification and a screenshot checklist.
6. **PR 6 — Login/accessibility pass:** show/hide, autofill, field errors, workspace picker, failure states.
7. **PR 7 — Canonical DB migration inventory:** report source-vs-live drift and restore missing applied migration sources without applying schema changes.
8. **PR 8 — First vertical workflow acceptance:** product → stock movement → sale/payment → ledger/journal/report in an isolated test fixture.
9. **PR 9 — Customers as a real module:** split customers from Sales/Commerce and cover list/profile/history/receivable read.
10. **PR 10 — Purchasing vertical slice design/API contract:** supplier → draft PO → approval → partial receipt, using recovered migration sources and role checks.

This sequence addresses the visible outage and starts giving real business value before heavy intelligence work. Run parallel tasks only after the API contracts and core types are stable (e.g. visual system work can proceed while migration inventory is being documented).

---

## 11. Product documentation to maintain from now on

The current project has many phase documents and release notes but no single up-to-date product truth. Add or maintain these top-level docs:

1. `PRODUCT_BRIEF.md` — target users, jobs-to-be-done, core promise, non-goals, country/localisation assumptions, pricing/rollout and product success measures.
2. `ARCHITECTURE.md` — frontend, API, Neon, queue/cache, authoritative data boundaries and diagrams; updated when route/module ownership changes.
3. `UX_STANDARDS.md` — layout, mobile behavior, login, standard page templates, accessibility, state/error semantics and screenshot breakpoints.
4. `MODULE_CATALOG.md` — each module’s user job, API endpoints, tables/permissions, current status, limitations, acceptance tests and owner.
5. `PHASE_ROADMAP.md` — increment list with status/commit/test proof; avoid stale labels “implemented” without a deployed acceptance gate.
6. `DATABASE_MIGRATIONS.md` or updated `migrations/README.md` — complete, ordered, reproducible migration inventory, applied version ledger and release path.
7. `AI_MODEL_POLICY.md` — data sensitivity, providers/model allowlist, pricing/privacy, task routing, fallback rules, prompt/tool/version governance and budget limits.
8. `AI_EVALUATION.md` — test cases, quality thresholds, model comparisons, latency/cost/unsupported-answer rates.
9. `OPERATIONS_RUNBOOK.md` — health/readiness, incident triage, session failure diagnosis, rollback, safe migration and production smoke tests.

The module catalog should use only four statuses: **Placeholder**, **In progress**, **Implemented (not production verified)** and **Production verified**. A feature moves to the last status only after the API, database, tenant permissions, UI states and hosted smoke test pass.

---

## 12. Source and research references

### Original LEXA project files reviewed

- `docs/PHASE_0_RECOVERY.md`
- `docs/PHASE_0_VERIFICATION_REPORT.md`
- `docs/PHASE_1.md`
- `docs/PHASE_2_AUTH_HARDENING_STATUS.md`
- `docs/PHASE_2_CATALOG.md`
- `docs/PHASE_2_UNIVERSAL_BUSINESS_ENGINE.md`
- `docs/PHASE_3_INVENTORY.md`
- `docs/PHASE_3_UI_UX_IMPLEMENTATION.md`
- `docs/PHASE_3_5_WORKSPACE_CONVERGENCE.md`
- `docs/PHASE_4A_END_TO_END.md`
- `docs/PHASE_4B_ACCOUNTING_EFRIS.md`
- `docs/PHASE_5_ANALYTICS.md`
- `docs/LEXA_EXPERIENCE_FOUNDATION_v1.4.2.md`
- `docs/LEXA_International_Research_Phase3.md`
- `docs/DEPLOYMENT_RENDER_VERCEL.md`
- `migrations/README.md`, `RELEASE_NOTES_2.8.0.md`, and the source migration tree.

### Live read-only operational evidence reviewed

- Render service `LEXA`, URL `https://lexa-n10e.onrender.com`, deploy of commit `010129d461bac0eef242a858e4d8d0210cf64d3c` reported live.
- Render log snapshot: `/health` and `/ready` return `200` in the observed window; `auth/refresh` gets repeated `422` when protected routes are returning `401`.
- Canonical Neon project `wispy-mud-75323042`, branch `br-soft-star-b1dj2m2w` (`lexa-live`), database `neondb`: read-only check of `schema_migrations`, `brain_*` tables and tenant policies. No writes were run.
- GitHub current source at commit `010129d461bac0eef242a858e4d8d0210cf64d3c`; no Git push or Vercel environment change performed.

### Current official model/platform documentation

- Google Gemini 3.8 Flash model card, stable model ID and context capabilities: https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
- Google Gemini API pricing and free/paid data-use terms: https://ai.google.dev/gemini-api/docs/pricing.md
- NVIDIA Nemotron 3.5 Lightning 30B A3B model card (release date, parameters, context): https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b/modelcard
- NVIDIA Nemotron 3 Ultra 550B A55B model card (parameters, hardware, context): https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard
- OpenRouter current free model catalog (October 2026, usage-ranked rather than quality-ranked): https://openrouter.ai/collections/free-models
- OpenRouter model fallback documentation: https://openrouter.ai/docs/guides/routing/model-fallbacks
- OpenRouter guardrails for model/provider allowlists, spend and data privacy: https://openrouter.ai/docs/guides/features/guardrails/overview
- DeepSeek API model identifiers and current pricing: https://api-docs.deepseek.com/quick_start/pricing/
- Next.js authentication guide: https://nextjs.org/docs/app/guides/authentication
- W3C WCAG 2.2 accessible authentication: https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum
- W3C WCAG 2.2 target-size minimum: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum
- W3C WCAG 2.2 error identification: https://www.w3.org/WAI/WCAG22/Understanding/error-identification
- FastAPI testing with TestClient/HTTPX: https://fastapi.tiangolo.com/tutorial/testing/
- statsmodels time-series forecasting examples: https://www.statsmodels.org/dev/examples/notebooks/generated/statespace_forecasting.html

**Research caveat:** Model availability, IDs, pricing, quotas, provider retention settings and policies can change after this snapshot. Re-check official pages and model catalog before enabling a provider in production. Competitor patterns and official model descriptions are inputs to LEXA’s decision, not proof that one model is best for LEXA. Choose models with LEXA-specific tests for answer accuracy, tool success, latency, cost and privacy.

---

## Final recommendation

Do not begin by implementing a dozen modules and several autonomous AI agents concurrently. First make the application reliable, then complete a few daily business journeys to production quality, then introduce read-only intelligence that explains verified facts. The fastest route is not the smallest amount of code; it is the smallest increment that a real user can use safely and reliably.
