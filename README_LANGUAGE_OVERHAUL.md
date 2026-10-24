# LEXA Language Overhaul — Corrected Source Overlay

**Target branch:** `main`  
**Package type:** source overlay for the existing LEXA ZIP extractor

## Why this package is different

The previous archive was skipped because it did not contain the two required LEXA source markers. This ZIP includes `apps/web/package.json` and `apps/api/app/main.py` byte-for-byte from the current `main` source, plus a temporary `migrations/` marker that the extraction manifest removes. It is structured for the existing repository extractor.

## Included source changes

- Replaces the AI Assistant form with a clear unavailable state and links to Sales, Stock, Reports, Purchases, Customers and Documents. It does not fetch provider configuration or imply that a reply can be generated.
- Renames navigation items and search suggestions to use familiar labels while preserving their existing route paths.
- Polishes the Daily overview and Document review copy, including safer user-facing errors and clearer document-reading status.
- Simplifies local document-reading warning messages without changing extraction behavior.
- Adds the approved whole-interface language standards and inventory.

## Safety

This package does not add or continue a product phase. It does not change business rules, database schemas, permissions, migrations, provider configuration, secrets, accounting effects, hosting settings, or deployments. Existing extractor workflow files remain untouched. The temporary marker is removed by `DELETE.txt` after successful extraction, and the old skipped ZIP is removed as part of the same successful extraction.

## Validation limits

Focused static language tests are included. This package has not been run through the full Next.js production build, full repository CI, or authenticated browser acceptance. The live site should only be considered updated after the extractor creates a new source commit and Vercel deploys that exact commit.
