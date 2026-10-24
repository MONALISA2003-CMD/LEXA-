# LEXA Intelligence Phase 3 — Document intelligence

**Status:** source overlay prepared; awaiting extraction, full repo checks, disposable database replay and staging acceptance. This document is not a claim of production acceptance.

## Goal

Turn invoices, receipts and purchase orders into **reviewable structured candidates**, so Ugandan SMEs avoid repetitive typing while keeping finance and stock records under normal LEXA controls. The feature is document workflow, not a chatbot and not automatic accounting.

## Flow

1. An authenticated member selects a permitted branch and document type and uploads a PDF, JPG, PNG or WebP file (maximum 10 MiB).
2. The API validates the declared MIME type and file signature, limits bytes streamed into memory, normalizes the filename and calculates SHA-256.
3. LEXA checks for a same-content duplicate within the tenant and branch. The database uniqueness constraint remains the final multi-replica arbiter.
4. Local PDF text extraction / OCR is attempted with a hard timeout. The implementation does not call an external AI provider. If a local binary is unavailable or extraction fails, the source file remains in manual-review state.
5. Label-based extraction proposes supplier/customer names, invoice/receipt/purchase-order numbers, document/due dates, subtotal, VAT/tax, total, currency and tax ID. A value includes the source line and a heuristic confidence marker. This score is not a calibrated probability and not proof of correctness.
6. The user checks candidate values against the original file, fills missing fields and confirms or rejects the document. The API validates field allowlists, date/amount/currency format and required fields by document type.
7. The confirmation creates a review-history record with actor, time, decision, reason and a fingerprint of the confirmed fields. It still does not create or post a domain transaction. The user continues in Purchasing or Finance and follows that module's existing validation/approval/posting workflow.

## API

Base prefix: `/api/v1/intelligence/documents`.

- `POST /intake` — raw file body plus `Content-Type`, `X-Document-Type`, `X-Branch-ID` and `X-Document-Filename` headers.
- `GET /` — list documents for allowed branches, optionally filtered by branch or status.
- `GET /{document_id}` — document metadata, candidate fields, source text preview and review state.
- `GET /{document_id}/file` — retrieve the original file as a no-store attachment.
- `POST /{document_id}/review` — explicit `CONFIRM` with reviewed fields or `REJECT` with a reason.

Permissions are `intelligence.documents.intake`, `.read` and `.review`; tenant identity is derived from the authenticated context, not client input. `X-Branch-ID` is independently verified against membership. No endpoint accepts arbitrary tenant IDs or model-provided SQL.

## Storage and safety

- Migration `046_intelligence_documents.sql` adds bounded binary storage, branch-scoped status/candidates and review-history tables.
- Both tables use forced RLS, branch access predicates, explicit grants and tenant/branch foreign-key constraints.
- File size is capped at 10 MiB; extracted text at 12,000 characters; candidate metadata and review history are bounded.
- Intake validates file signatures before running local parsers. Subprocesses use `shell=False`, fixed executable names, a restricted environment and hard timeouts.
- Output labels extracted text as candidate evidence; customer/supplier matches are not created automatically.
- Review history is granted insert-only to `lexa_app`; the application role cannot delete or rewrite history.
- External AI execution remains blocked by the API middleware until a future increment explicitly wires the route to the LEXA policy router and privacy controls. Adding a provider key does not unblock the current assistant.

## Phase 1 and 2 integration

- Phase 1 contracts/policy and migration `045` are carried at canonical application paths.
- Phase 2's daily-brief builder and API are registered in `main.py`, and the new `/daily-brief` web route calls the tenant-authenticated API.
- Phase 3 adds the `/documents` route, review UI and navigation entry.
- AI Assistant copy is revised to plain-language business guidance, with a clearly explained paused state and no false promise that a provider is active.

## Runtime OCR dependency

The service reports availability of `pdftotext`, `pdftoppm` and `tesseract` under `/api/v1/intelligence/capabilities`. The included `apps/api/Dockerfile` now installs `poppler-utils` and `tesseract-ocr`, so OCR tools are present when that Dockerfile is used. The currently inspected Render service configuration uses the Native Python runtime (`render.yaml` says `runtime: python`), and Native Python does not guarantee these binaries. The Dockerfile change alone does not switch an already-configured hosted service to Docker. Until a maintainer separately reviews and approves that service-runtime change, hosted uploads may fall back to manual review. This bundle deliberately does not change hosted service type or trigger a deployment.

## Acceptance checklist

- [ ] ZIP extractor writes source at canonical paths and creates an extractor commit on the intended branch.
- [ ] Existing API tests and web tests/typecheck/build pass for the exact source SHA.
- [ ] Clean replay applies migrations 045 and 046 to a disposable PostgreSQL database.
- [ ] Database checks prove forced RLS and branch isolation for both tables, insert-only review history and no cross-tenant access.
- [ ] API upload rejects disallowed MIME, mismatched file signatures, empty files, over-limit body and unassigned branches.
- [ ] Same-file upload is idempotent under a multi-replica race.
- [ ] Synthetic PDF and image tests validate parsed values/evidence and manual fallback; no request leaves the service for OCR/model processing.
- [ ] Authenticated browser test covers upload, duplicate response, view original, edit fields, confirm/reject and responsive screens.
- [ ] Real domain workflows still own invoice/expense/purchase-order creation, posting, EFRIS and financial entries.
- [ ] Provider execution remains disabled unless a separately approved policy-gated integration is delivered.

## Out of scope

No automatic invoice posting, payment creation, automatic supplier/party matching, bank/Mobile Money connection, EFRIS system integration, generative model extraction, vector database, background AI job execution or live data migration is enabled by this increment.
