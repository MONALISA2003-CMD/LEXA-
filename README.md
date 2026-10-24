# LEXA CI fixes + Intelligence — Phase 1 + Phase 2 + Phase 3 source overlay

**For the LEXA ZIP Extractor: upload this ZIP to `main`.** It is an overlay ZIP with the required LEXA source markers at the archive root (`apps/web/package.json`, `apps/api/app/main.py`, and `migrations/`). It is not a standalone installer and does not contain secrets.

## CI root causes fixed

This bundle also addresses the failures observed in [Actions run 40063918855](https://github.com/MONALISA2003-CMD/LEXA-/actions/runs/40063918855): a nullable daily-brief currency access, provider `.env` fields missing from Pydantic `Settings`, and historical migration tests incorrectly requiring migration 044 to remain the last entry. See `docs/LEXA_CI_ROOT_CAUSES_AND_PHASE1_3_VALIDATION_2026-10-24.md`.

## What this increment contains

- **Phase 1 — intelligence foundation:** strict shared contracts, policy-only AI router, default-deny external AI, safe capability reporting, durable job/run provenance migration candidate `045`.
- **Phase 2 — daily business brief:** deterministic seven-day brief over LEXA's existing saved insight calculations, a dedicated `/daily-brief` workspace, currency-aware metrics, evidence links and a separate data-quality section.
- **Phase 3 — document intelligence:** branch-scoped PDF/image intake, SHA-256 duplicate detection, bounded local text/OCR extraction, candidate fields with supporting text, editable human confirmation/rejection, append-only review history and a responsive `/documents` workspace.
- **AI Assistant language polish:** everyday business wording and an explicit paused state while external AI policy execution is not enabled. Provider keys alone do not permit model execution.

## How it is designed to behave

- Document extraction returns **candidates**, not verified accounting/purchasing values.
- Every document is saved as `NEEDS_REVIEW`; the UI asks a team member to check the original source and confirms fields only after that explicit review.
- Confirming a document does not create an invoice, expense, purchase order, payment, journal entry, inventory movement or EFRIS submission. The normal domain workflow remains the only write path.
- Original files, candidate rows and review history are tenant/branch-scoped in PostgreSQL with forced RLS. Identical file hashes in a branch are treated as duplicates.
- Local parsing uses `pdftotext`, `pdftoppm` and `tesseract` only when those binaries exist. `/api/v1/intelligence/capabilities` reports tool availability. If they are unavailable, LEXA keeps the file for manual entry/review rather than sending document contents to an external provider.
- External model calls, durable worker execution, automatic business writes and paid fallbacks stay disabled.

## ZIP behavior

The archive root intentionally contains the canonical `apps/` and `migrations/` paths the existing extractor checks for. The ZIP does not ask the extractor to modify `.github/workflows/` and does not include `.env` or secrets. On successful extraction, inspect the generated `[lexa-extractor]` commit and status checks for the exact resulting SHA.

## Validation boundary

The included synthetic checks validate pure Python contracts, OCR/field extraction behavior, migration/source contracts, and web integration assumptions. They do not prove a full repository CI run, Next.js production build, database migration replay, cross-tenant runtime RLS behavior, or authenticated staging acceptance. Migration files `045` and `046` are forward-only candidates and must be reviewed and clean-replayed on a disposable PostgreSQL database before any production migration decision.

The connected GitHub integration in this session was read-only for branch writes, so this ZIP was not committed directly. No production database, API keys, hosted settings, deployment or provider account was changed.
