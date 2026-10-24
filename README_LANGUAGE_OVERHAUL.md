# LEXA Full Business-Language Overhaul

**Target:** `main` in `MONALISA2003-CMD/LEXA-`  
**Baseline inspected:** `36f894b0b0e9203840a333548980e569502cc8c7`  
**Audience:** small-business owners, managers and staff in Uganda.

## What this package contains

- A plain-English language standard and module-by-module inventory covering Home, Sales/Checkout, Stock, Products, Customers, Purchases, Money & records, Reports, Business details, Team access, Tax/EFRIS, the Daily overview, Sales forecast, Documents, Business assistant, Sign-in and shared notices.
- An idempotent wording-application script. It changes visible copy and language-focused test expectations only; it does not intentionally change accounting calculations, tax behaviour, APIs, access rules, provider settings or data.
- A full-check workflow template and language regression test asset. The workflow applies the wording pass on the **current main checkout**, then runs full frontend typechecking/tests/build, the API test suite and deployment-configuration checks. It commits the changes only when all checks pass.

## Required installation steps

**Important:** LEXA's existing ZIP extractor intentionally protects `.github/workflows` and will skip workflow files placed at that path inside a ZIP. The included workflow is therefore stored at `docs/LEXA_LANGUAGE_OVERHAUL_WORKFLOW.yml`, not as an active GitHub workflow yet.

1. Upload this ZIP file itself to the repository root on `main`. Let the existing LEXA ZIP extractor finish. The ZIP includes the exact `apps/web/package.json` and `apps/api/app/main.py` marker files from the inspected baseline so the extractor recognizes it. It also removes the temporary marker and an obsolete archive listed in `DELETE.txt`.
2. On GitHub, create `.github/workflows/lexa-language-overhaul.yml` on `main`. Copy the full contents of `docs/LEXA_LANGUAGE_OVERHAUL_WORKFLOW.yml` into that new file and commit it. This manual step is required because the extractor protects the workflow directory.
3. Open **Actions → LEXA Full Business Language Audit → Run workflow**, choose `main`, confirm the update input, and start it.
4. The workflow applies the word changes to the full current `main` source. It runs typecheck, all frontend tests, the production build, all API tests, Compose validation and HAProxy checks. It pushes the wording commit only when every check passes, then starts the standard main CI workflow.
5. Review the new main commit and standard CI result before treating the language pass as complete. Confirm Vercel and Render deploy the intended commit. No Neon schema or business data change is part of this pass.

## Why the workflow is not active yet

The GitHub connection available to this assistant has no repository write permission (`403 Resource not accessible by integration`). Direct Vercel Sandbox creation was also unavailable because the account reached its snapshot-storage limit. The source application and full checks are therefore **not claimed as already committed or green**. Installing the template through the repository UI is the supported route to execute the complete pass.

## Product-language rules

- Use short, natural sentences and familiar business words. Do not expose software-engineering terminology in ordinary business screens.
- Keep meaningful terms such as invoice, receipt, VAT, refund, amount due and recorded payment accurate.
- Explain statuses honestly; missing information is not zero, and an unsuccessful save is not reported as successful.
- Do not expose provider names, keys, model choices, quotas, pricing or internal configuration.
- The Business assistant stays unavailable and does not send questions or change business records as part of this language pass.
