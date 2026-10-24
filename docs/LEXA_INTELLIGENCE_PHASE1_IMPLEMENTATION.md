# LEXA Intelligence — Phase 1 implementation package

**Scope:** shared intelligence contracts, event normalization, LEXA-owned provider policy, tenant-safe persistence foundation, capability discovery, and a synthetic test harness. This package does not implement Phase 2's daily brief, Phase 3 document extraction, Phase 4 forecasting, action execution, or a new hosted service.

**Deployment state:** source bundle only. It has not been committed upstream, run against a LEXA database, enabled in Render/Vercel, or deployed. The GitHub connector rejected branch creation due to integration permissions. The migration is a reviewed candidate, not an applied migration. Phase 0 remains considered complete as directed by the user.

## What is implemented

- Strict Pydantic v2 contracts for tenant scope, source references, metrics, evidence, insights, event envelopes, job references, and routing decisions. Unknown fields are rejected.
- A central deterministic policy function with explicit external-provider allowlist, separate paid-provider opt-in, aggregate/confidential-data controls, personal-data block, task-to-provider profiles, and no automatic fallback.
- Deterministic business-insight and replenishment tasks remain local; forecasting explicitly reports `CAPABILITY_NOT_IMPLEMENTED` rather than pretending an implementation exists.
- Read-only `GET /api/v1/intelligence/capabilities`, requiring the existing `analytics.read` permission. It does not load business rows or contact an AI provider.
- A legacy `/api/v1/ai/assist` policy gate. The new server settings default to external AI disabled. For requests to pass, the global flag, explicit provider allowlist, key configuration, task compatibility, and sensitivity approval must all pass.
- Additive SQL candidate `045_intelligence_foundation.sql` creating tenant-/branch-scoped `intelligence_jobs` and `intelligence_runs` with RLS, bounded allow-listed reference metadata, idempotency, status/provenance, and least-privilege table grants. Jobs can be updated by the future worker; run records are append-only for the runtime role. No raw prompts, OCR text, model outputs, secrets, or write instructions belong in those rows.
- Synthetic unit tests that use no network and no real customer/business data.

## Installation

From a clean local checkout of `MONALISA2003-CMD/LEXA-`, run:

```bash
python path/to/LEXA_PHASE1_IMPLEMENTATION/scripts/apply_phase1.py --repo-root /path/to/LEXA-
```

The installer copies new files and applies narrowly anchored edits to `apps/api/app/config.py`, `apps/api/app/main.py`, and `apps/api/app/routes/ai_assistant.py`. It is idempotent for already-applied edits; it stops if an expected source anchor is absent or ambiguous rather than guessing. Review the resulting diff before committing it. It does not contact GitHub or any infrastructure service.

Run the focused synthetic suite:

```bash
cd apps/api
pytest -q tests/test_intelligence_phase1.py tests/test_ai_assistant.py
```

The package also contains the expected migration file at `migrations/045_intelligence_foundation.sql`. The standard clean migration replay/manifest should be updated and run in disposable CI according to LEXA's existing migration workflow; **do not run this SQL against production directly**. The migration checks prerequisites and records version `045_intelligence_foundation`.

## Server configuration: fail-closed defaults

No new provider should be switched on during Phase 1. The following server-side settings default to `false`/empty, so environment variables do not need to be added to deploy Phase 1 safely:

| Environment variable | Default | Meaning |
|---|---:|---|
| `LEXA_AI_EXTERNAL_PROVIDERS_ENABLED` | `false` | Global gate for all API-exposed external AI calls, including the legacy assistant. |
| `LEXA_AI_ALLOWED_PROVIDERS` | empty | Explicit comma-separated provider IDs; e.g. `gemini,groq` only after approval. |
| `LEXA_AI_PAID_PROVIDERS_ENABLED` | `false` | Additional opt-in required for OpenAI, OpenRouter, Cerebras, and Hugging Face provider profiles. |
| `LEXA_AI_AGGREGATES_EXTERNAL_ENABLED` | `false` | Approval flag for transmitting non-identifying business aggregates externally. |
| `LEXA_AI_CONFIDENTIAL_EXTERNAL_ENABLED` | `false` | Approval flag for confidential business data. Keep false until provider terms, retention, legal basis, and cross-border processing are reviewed. |

The global flag and allowlist are both required. A provider key alone never enables routing. An explicit provider choice does not silently fall back to another provider when unavailable or quota-limited. The policy blocks identifiable and sensitive personal data from external routing even if other flags are enabled, and an additional internal `input_safety_checked` signal must be set by trusted server-side screening code.

**Important Phase 1 boundary:** that trusted screening/redaction pipeline is not implemented yet. Therefore the existing free-text `/api/v1/ai/assist` endpoint remains blocked even if an operator turns on the configuration flags. The status endpoints report execution as disabled. This is intentional: Phase 1 must not pretend that arbitrary user text has been screened for personal information. A later phase can enable a typed workflow only after server-side classification, provider terms, privacy and cross-border reviews, and synthetic/adversarial tests are complete.

Provider account billing is an external control: Gemini/Groq may have account-specific limits or billing. Do not infer that an API key guarantees zero cost. Keep external providers disabled until the operator has confirmed the specific provider plan and privacy terms.

## Tenant and branch boundaries

- Tenant identity and user identity come from LEXA authentication/dependencies, not caller-controlled body fields.
- Job and run tables have forced RLS and require `app.tenant_id`; branch-scoped rows also use `lexa_can_access_branch`.
- Inputs are record references and allow-listed metadata, never broad row dumps or raw documents.
- Event normalization names are contract names for future adapters. The schema does not claim that current sales/purchasing/finance outbox emitters already publish all of them.
- Cross-tenant summaries, caches, vector retrieval, and model memory are not introduced in Phase 1.

## What Phase 1 deliberately does not do

- It does not start a job worker, connect the new jobs table to the current outbox, add any provider SDK, or perform model calls from `/intelligence/capabilities`. All provider execution remains disabled in Phase 1.
- It does not create or post sales, receipts, invoices, purchase orders, payments, journals, inventory adjustments, or fiscal documents.
- It does not treat an LLM response as financial truth or allow arbitrary SQL/tool execution.
- It does not claim live URA/EFRIS system-to-system integration.
- It does not apply database migrations or change Render, Neon, Vercel, CI secrets, or production configuration.

## Acceptance checklist

- [ ] Install into the current repository and review the complete diff.
- [ ] Run `pytest -q tests/test_intelligence_phase1.py tests/test_ai_assistant.py`.
- [ ] Run the existing API test suite, lint/typing checks, and normal CI.
- [ ] Add `045_intelligence_foundation` to the disposable migration replay/manifest and verify RLS adversarially under the runtime role.
- [ ] Confirm no migration was run against live Neon and no provider setting was enabled.
- [ ] Verify unauthenticated and unauthorized requests cannot access `/api/v1/intelligence/capabilities`.
- [ ] Verify `/api/v1/ai/assist` returns policy-disabled even if provider flags are toggled, because the trusted input-screening path is not yet implemented; this must happen before rate-limit, business-summary query, or provider network I/O.
- [ ] Verify provider status contains no API keys, prompts, document data, or customer identifiers.

The capability endpoint can be enabled with normal application deployment only after code review. Applying migration 045 and enabling external AI are separate decisions and require explicit approval.
