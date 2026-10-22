# LEXA Phase 4 — Release Acceptance Matrix

**Candidate date:** 21 October 2026  
**Disposition:** Implementation candidate prepared; hosted release acceptance remains pending. Phase 5 planning/development may proceed, but do not promote this candidate to production yet.

| Gate | Evidence from this work | State |
|---|---|---|
| Dashboard UX and chart contract | 24 frontend source-contract tests pass after this update. Chart labels describe net sales vs payments collected; selected date ranges and data-table alternative are present. | PASS — source contract |
| Dashboard data correctness | Today's collected value now aggregates `RECORDED` payments by workspace business date/currency; inventory valuation and exception counts aggregate all authorized balances server-side; monetary format follows workspace currency. | PASS — source-level checks |
| Inventory authorization | Summary uses `accessible_location_ids` plus tenant predicates and tenant-safe product/location joins; detail/attention records have separate limit. | PASS — source contract only |
| Backend suite | 27 tests pass. One auth-refresh integration test is skipped because required API test dependencies are not installed in this runner. | PASS WITH SKIP |
| Python compilation | `compileall` for API application and tests passes. | PASS |
| Migration source manifest internal checks | Recovery manifest/hash/separation check passes. | PASS — manifest integrity only |
| Historical migration canonical-byte parity | Six exact historical sources remain replaced under the previously accepted loss/substitution decision. This candidate adds no schema migration. | ACCEPTED POLICY GAP — strict provenance/replay not proven |
| Node 24 clean install | This runner only has Node 22.16.0; `npm ci --offline` fails because `undici-types@6.21.0` is not cached and registry DNS/network is unavailable. | BLOCKED — environment |
| Full TypeScript typecheck and Next production build | Cannot be verified without the clean dependency-complete installation. A standalone TypeScript transpilation-only pass parsed 33 `.ts`/`.tsx` files with zero syntax diagnostics; that is not a typecheck/build. | BLOCKED — environment |
| Playwright/authenticated browser acceptance | An opt-in test is packaged for a dedicated, non-production QA storage state, but Playwright is not a direct installed app dependency in this environment and no authenticated run was executed. | NOT RUN |
| Vercel isolated Node 24 runner | Vercel returned HTTP 402: Hobby snapshot-storage quota exceeded; usage limit reset shown as 1 November 2026. Existing session has no snapshot to resume. | BLOCKED — requires account quota resolution or another authorized Node 24 runner |
| GitHub branch/commit | Connected GitHub reader verified shared stable base file hashes, but write permission is unavailable (`Resource not accessible by integration` from prior attempt). Changes are not committed to `main`. | BLOCKED — access |
| Preview deployment / live smoke acceptance | No new preview build was deployed from this candidate. Production data/configuration were not changed. | NOT RUN |

## Release gate to unblock Phase 5 execution

Required on an authorized Node 24 environment, using the Phase 3 final-cutover source as the base and this Phase 4 overlay:

```bash
cd apps/web
node --version                 # must report v24.x
npm ci
npm run typecheck
npm test
npm run build
```

Then install the optional Playwright dev dependency through an authorized lockfile update, provide `LEXA_PHASE4_STORAGE_STATE` for a non-production QA user, and run the documented E2E suite against the preview URL. Validate at desktop and 390px mobile widths, keyboard focus, permissions, analytics dates/currency and the new inventory summary. Confirm Render/Vercel commits/configuration remain aligned before promotion.

The Phase 4 source implementation is ready for controlled CI/preview validation. A full production-release pass cannot be claimed until the blocked gates above have successful evidence.
