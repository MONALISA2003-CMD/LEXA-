# LEXA live brand visibility fix — upload guide

## Why this package exists

The current production build is reachable and GitHub CI is green, but inspecting the active Vercel CSS showed the mobile header still using the retired compact L mark with plain "LEXA" text, while primary buttons still resolve to the previous green gradient. The desktop sidebar was displaying only the cropped wordmark without the full gold descriptor. CI had checked compilation and static contracts, not the actual visual result.

## What this ZIP changes

- Uses `/lexa-master-logo.jpg` in the desktop/open-mobile sidebar and authentication brand area, including the complete gold descriptor.
- Uses `/lexa-wordmark-master.jpg` for the persistent mobile header instead of the old compact-mark-plus-text composition.
- Adds final high-specificity palette overrides so primary actions are blue, positive state green remains semantic, dashboard KPI cards have a clear hierarchy, and line/bar chart series are deliberately styled.
- Adds `tests/phase12-live-brand-visibility.test.mjs` to prevent the exact visibility regressions found in the live CSS.
- Keeps all API business logic, access rules, and database migrations unchanged. Required source marker files are included only so the established ZIP extractor recognizes the archive; those marker files match the current main branch.

## Apply

Upload this ZIP (not an extracted folder) to the root of `MONALISA2003-CMD/LEXA-` on `main`. Wait for `LEXA ZIP Extractor` to finish and commit its `chore: extract canonical LEXA source [lexa-extractor]` commit. Then check `LEXA Main Build CI` and the Vercel production deployment built from that *extractor commit*.

## Verify production visually

After the new deployment is READY, reload `https://lexa-green.vercel.app/` without a cached app view. Check (1) the full master logo in the desktop sidebar, (2) the official colour wordmark in the mobile header, (3) full master artwork on sign-in/registration, (4) blue primary actions, (5) dashboard KPI hierarchy, (6) blue net-sales and dashed cyan/blue-cyan collected-payment line, (7) comparison bars, and (8) responsive chart stacking at 800px and 520px. Do not treat a green CI badge alone as visual acceptance.

This ZIP has not been deployed by itself. Production is only updated when the extractor commits the source changes and Vercel publishes that commit.
