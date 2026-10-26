# LEXA Brand Authority — ZIP Extractor Ready Upload

## Why this package is different

The repository's `.github/workflows/lexa-zip-extract.yml` does not extract arbitrary frontend-only ZIPs. It validates a package as a canonical LEXA source archive only when it includes these exact repository paths:

- `apps/web/package.json`
- `apps/api/app/main.py`
- at least one file under `migrations/`

The earlier ZIP contained only frontend overlay files, so the extractor skipped it. GitHub and Vercel could still report green because the ZIP itself was committed and the unchanged app built successfully.

This archive now includes the required markers as byte-for-byte copies of the current `main` source, plus the actual frontend overlay. Their Git blob IDs were checked against the files currently on `main`; they are unchanged markers, not backend or migration changes.

## How to apply this package

1. Upload **this ZIP file itself** to the repository root (`MONALISA2003-CMD/LEXA-`) on branch `main`, using the filename `LEXA_BRAND_AUTHORITY_SOURCE.zip`.
2. Let **Actions → LEXA ZIP Extractor** run. It should recognize and extract the canonical `apps/web/...` paths, remove the processed ZIP from the working tree, commit the extracted frontend changes with `[lexa-extractor]` in the message, and dispatch the canonical LEXA CI workflow.
3. Wait for the extractor and `LEXA Main Build CI` workflows to finish. Vercel may first deploy the archive-only commit; that intermediate deployment is expected to look unchanged. The meaningful deployment is the later deployment whose commit message contains `chore: extract canonical LEXA source [lexa-extractor]`.
4. Open the **latest production deployment** and verify `https://lexa-green.vercel.app/`, `/login`, and these assets:
   - `/lexa-master-logo.jpg`
   - `/lexa-wordmark-master.jpg`
   - `/lexa-app-mark.png`

If the extractor fails, open the workflow run and read the first error before trying a different package. Do not manually run database migrations or alter backend environment variables for this frontend release.

## Files changed by the frontend overlay

- `apps/web/app/layout.tsx`: imports the shared brand-authority stylesheet and updates title, description and icon metadata.
- `apps/web/app/lexa-brand-authority.css`: global identity, shell, dashboard, operations, authentication and responsive brand rules.
- `apps/web/public/lexa-master-logo.jpg`: original supplied master art.
- `apps/web/public/lexa-wordmark-master.jpg`: horizontal wordmark crop for the sidebar.
- `apps/web/public/lexa-app-mark.png`: compact derived app mark.
- `apps/web/public/lexa-logo.svg`, `lexa-logo-light.svg`, `lexa-mark.svg`: preserve legacy asset paths while pointing to official derivatives.
- `apps/web/tests/phase10-brand-authority.test.mjs`: brand contract tests.

`apps/web/package.json`, `apps/api/app/main.py`, and `migrations/001_phase1_foundation.sql` are included only because the installed ZIP extractor requires canonical source markers. They are exact copies of `main`, verified against GitHub blob IDs, and should produce no content changes. No API logic, database schema, migration behaviour, environment variables, or financial records are intentionally changed.
