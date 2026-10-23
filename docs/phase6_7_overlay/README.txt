LEXA PHASE 6 & 7 — implementation acceptance overlay

Contents:
- apps/web/e2e/global-setup.ts: fail-closed guard before write-enabled inventory/purchasing E2E.
- apps/web/e2e/phase6-inventory-acceptance.spec.ts: replenishment math, scope and stock non-mutation.
- apps/web/e2e/phase7-authorization-acceptance.spec.ts: unauthorized branch list/detail/cancel probe.
- apps/web/playwright.config.ts and apps/web/package.json: register targeted tests and disable replay retries for staging writes.
- apps/web/tests/phase6-7-acceptance-safety.test.mjs: static tests for guard behavior.
- docs/*.json and docs/PHASE6_7_IMPLEMENTATION_CLOSEOUT_2026-10-23.md: fixture templates and handoff.
- workflow_install_required/.github/workflows/lexa-ci.yml: a proposed workflow that must be manually installed because the current GitHub ZIP extractor protects .github/workflows.

This is an additive ZIP overlay for MONALISA2003-CMD/LEXA-. It is NOT a complete source repository and must not be uploaded alone to the current GitHub ZIP extractor: it will not contain apps/api/app/main.py and will be skipped. Merge it into a full source checkout/archive first. The workflow under workflow_install_required must be copied by a maintainer with workflow permissions into root .github/workflows/lexa-ci.yml; ZIP extraction will skip workflow changes. No cloud CI or staging E2E pass is claimed. Never use production hostnames or production credentials for write-enabled tests.
