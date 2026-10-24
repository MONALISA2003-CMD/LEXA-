# LEXA origin forensics: Phase 0, Phase 1, Phase 2

**Audit date:** 24 October 2026 (UTC)  
**Repository:** https://github.com/MONALISA2003-CMD/LEXA-  
**Current inspected source commit:** `3374011ecef4974cfb036089eb53927bdb0900b0`  
**Failed Main Build CI:** https://github.com/MONALISA2003-CMD/LEXA-/actions/runs/40108630422

## Findings from the failing run

- API unit/contracts: **success** (the API job completed successfully).
- Docker Compose/HAProxy: **success**.
- Web typecheck: **success**.
- Web contract suite: **95 passed, 4 failed out of 99**; production Next.js build was skipped because the contract step failed.
- The four failure causes observed in the log were stale contracts, not compiler errors: (1) assistant privacy wording, (2) Phase 5 E2E matcher still expected the pre Phase 2 test pattern, (3) staging guard test expected the old `allowedHosts` variable rather than the actual shared guard variable `allowed`, and (4) Phase 7 E2E matcher still expected the pre Phase 2 pattern.

This patch updates only those expectation mismatches and the corresponding accessible privacy sentence. It does not remove HTTPS, production-host denial, separate authenticated storage-state, disposable-tenant, readiness, no-retry, tenant or branch-scope assertions.

## Phase 0 audit

**Still incomplete:** a clean, ordered migration replay against a fresh isolated database with authoritative provenance; full same-SHA CI including Next production build; authenticated staging transaction acceptance; measured assistant end-to-end latency; and a verified production source/API pairing.

The production DB was reported in the prior evidence packet to have already had migrations 045–047 applied and all 134 public base tables with RLS enabled and forced. That is not a substitute for clean replay. This ZIP runs no SQL and adds no migration. Production business tables previously inspected were empty for sales, payments, inventory transactions, journal entries and analytics metrics; empty metrics must remain unavailable, not fabricated as zero.

## Phase 1 audit

The source overlay includes server-side AI policy routing, allowlisted provider execution, question-only external prompt transmission, shared rate limiting, local factual answers from scoped/fresh read-only projections, source/freshness metadata, and UI disclosures. API tests and frontend typecheck passed in the most recent failed workflow, but the source has not passed the full release gate because the frontend contract step failed and the production build was skipped. No claim is made that a real external-provider call or a saved-data answer has been validated in a signed-in staging session.

## Phase 2 implementation and acceptance

- A read-only `GET /api/v1/commerce/sales/{sale_id}/evidence` endpoint checks `sales.read`, tenant ownership, and branch membership. It returns bounded event/audit metadata and an idempotency count but not outbox payloads or idempotency key values.
- The opt-in Playwright staging scenario checks checkout, duplicate-safe retry, stock movement and cost valuation, revenue/tax and COGS journals, balanced journal lines including both payment journals, partial payment/receivable, idempotent receivable settlement, sanitized outbox/audit evidence, and analytics before/after refresh.
- It is skipped unless a dedicated HTTPS staging host, disposable fixture, authenticated QA state, and explicit opt-in are configured. A production DB is not a valid fixture.
- Current CI contracts validate the route and guard configuration. The authenticated scenario itself has **not** yet been run; Phase 2 cannot be called accepted until its staging run passes and its evidence is tied to the exact deployed commit.

## Phase 3 integration boundary — no external payment/EFRIS APIs

The product decision is to avoid paid URA EFRIS, mobile-money and payment-gateway integrations. No URA, bank, mobile-money or gateway API adapter, webhook, provider credentials, status poller or payment execution has been added. Existing payment channels are business-record labels only. The old fiscalisation POST is blocked with `409 EFRIS_MANUAL_ONLY`; the old config endpoint rejects every mode other than `MANUAL`. Manual fiscal-document records are stored as draft and marked unverified by LEXA.

Official URA sources are used as static, dated reference material for local Python/Decimal estimates: https://ura.go.ug/en/ask-ura-commissioner-general-41/ (23 October 2026), https://ura.go.ug/en/changes-to-paye-return-form-following-the-income-tax-amendment-act-2026/ (7 September 2026), and https://ura.go.ug/en/additional-taxpayers-required-to-use-efris/ (August 2026). VAT-registration threshold values conflict between URA's October FAQ (UGX 300m) and the Government of Uganda VAT page (UGX 250m); LEXA discloses that conflict and does not infer registration status. The full Phase 3 behaviour is documented in `PHASE3_URA_AND_MOBILE_MONEY_INTEGRATION_GATES.md`.

## Patch validation after the forensic fix

- Updated the assistant privacy line to match the existing product-language contract: “This chat stays in this page and is not saved as conversation history.”
- Split Playwright matching into explicit Phase 2 and Phase 5–8 patterns. This preserves all suites while making the Phase 2 scenario selectable without invalidating established Phase 5/7 contract assertions.
- Renamed the common staging guard local to `allowedHosts` to match the existing safety contract; the HTTPS requirement, production-host deny list, disposable-tenant requirements, auth-state checks, readiness probe, and no-retry behavior remain intact.
- Added the dedicated `test:e2e:phase2` package command. Strengthened the scenario to assert balanced persisted debit/credit lines for sale recognition, COGS and payment journals, plus the ledger total-cost formula.
- Re-ran the three focused Node contract files locally: **4 tests passed, 0 failed**. Python compilation of all included changed API modules/tests passed. The Phase 2 API route registration/privacy contract is part of that focused run.
- The ZIP includes root-level `apps/api/app/main.py`, `apps/web/package.json`, and `migrations/` markers required by LEXA ZIP Extractor; generated Python/pytest caches are excluded.

These are targeted checks of the package contents, **not** a substitute for the full repository's CI. The complete 99-test frontend suite and Next production build must be rerun by GitHub after extraction. The authenticated staging write journey has not been executed because no disposable staging fixture and QA credentials were supplied.


## Phase 3 direction and implementation (24 October 2026)

The earlier integration-gates discussion below is superseded by the current product decision: **do not build paid URA EFRIS, mobile-money, or payment-gateway integrations**. LEXA records payment method/amount/reference without moving money. Tax calculators run locally in Python/Decimal. Official EFRIS documents are obtained separately through URA and may be copied into LEXA as audited manual records flagged `NOT_VERIFIED_BY_LEXA`; fiscal submission is blocked. The compliance settings endpoint rejects non-manual mode.

The local calculators cover VAT inclusive/exclusive, published presumptive-tax bands, resident/non-resident PAYE, and withholding estimates conditioned on confirmed withholding-agent status. Standard 18% VAT is applied automatically at checkout only after the owner confirms applicability and activates an effective-dated default rule with the correct price treatment. The 23 October 2026 URA FAQ gives UGX 300m as a VAT threshold while the Government VAT page gives UGX 250m; the product explicitly discloses this conflict and never infers registration from turnover. See `PHASE3_URA_AND_MOBILE_MONEY_INTEGRATION_GATES.md`.

Local target tests were added for all calculation bands, eligibility fail-closed paths, manual EFRIS restrictions and record-only payments. This package must still be extracted and pass the complete CI workflow on the resulting commit; local targeted test success must not be described as full CI success.

## Deployment inspection before this Phase 3 overlay

The base commit before this tax/manual-only overlay is `085eee35fdc93d736d2febea7ad9c09967c94e72`. The user reports its GitHub CI is green and Vercel is deployed/green. In the approved Render workspace, service `LEXA` (`srv-dakm8k95efls73egg9a0`) was manually deployed to the same SHA as deployment `dep-dbeei7u7bikc7386obh0`; Render reported `live` and the build succeeded. The live readiness response returned HTTP 200 with `status=ready`, `database=ok`, and `cache=ok`. These are baseline checks only: the Phase 3 source changes in this ZIP are not yet on that deployed SHA and require their own CI/deployment verification after extraction.

## Exit criteria still required

1. Re-extract this bundle and verify canonical `apps/api/...` and `apps/web/...` changes, not a nested `source/` directory.
2. Get **0 contract failures** on the resulting SHA; then verify API tests, typecheck, **production build**, Compose and HAProxy all pass.
3. Provision and execute the authenticated Phase 2 journey against an isolated staging tenant; capture the deployed SHA plus transaction/journal/stock/outbox/analytics assertions.
4. Compare Render API and Vercel web deployed SHAs and smoke-test readiness/login/assistant; do not describe either service as bug-free based only on `LIVE`/`READY`.
5. Phase 3 intentionally does not require URA or payment-provider API onboarding. Verify tax calculators and manual-only recordkeeping, and use the official URA portal separately for any mandatory EFRIS documents.


## Latest CI follow-up — run 40114334149

After the prior audit, the next Main Build CI run checked out commit `1e93fc87022bf7d31cae0ae00c537371af148ccb`. API contracts and Docker/HAProxy passed, and web typecheck passed. The web test run reported 97 passed and 2 failed of 99; both failures were stale expectations in the Phase 5 and Phase 7 test contracts for a former combined Playwright matcher. The source config now has separate Phase 2 and Phase 5–8 matchers. Those two assertions are corrected in this bundle. This failure stopped the Next production build from running. See `RUN_40114334149_FORENSICS.md` for the exact root cause, changes and current deployment evidence.

The patch has not yet been applied to GitHub main by this assistant: the connected GitHub integration returned HTTP 403 when attempting to create a branch. The verified ZIP is therefore an upload/extractor patch. A new GitHub CI run is still required to certify that the resulting commit has no failures.


## Phase 3 local tax/manual-only verification (24 October 2026)

The current Phase 3 overlay adds a pure-Python `Decimal` calculator for 18% VAT inclusive/exclusive, presumptive tax bands/eligibility, resident/non-resident PAYE effective 1 July 2026, and qualified-agent withholding estimates. A permission-protected endpoint returns tax estimates locally. EFRIS submission is blocked; manual tax-document entry is audited and stays `DRAFT` plus `NOT_VERIFIED_BY_LEXA`. Payment methods remain recording labels only; no money movement, provider webhooks, status polling or EFRIS/mobile-money/payment-gateway API adapter is added.

Verification performed on the overlay: **13 Python tests passed**, **5 Node contract tests passed**, changed API modules compile, and the compliance page TypeScript syntax transpile has zero diagnostics. This is targeted validation, not the complete web suite or production build. Full GitHub CI and authenticated staging acceptance are still required after the ZIP is extracted. The VAT threshold discrepancy is preserved explicitly: URA's October FAQ says UGX 300 million while a Government of Uganda VAT page says UGX 250 million; LEXA does not use either number to auto-decide registration.
