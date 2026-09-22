# LEXA Experience Foundation v1.4.2

This release completes the experience hardening pass around workspace authentication, responsive interaction states and canonical database selection.

## Customer experience

The browser experience uses the LEXA brand assets throughout the public and authenticated surfaces. Authentication now supports password visibility, focus management, escape-to-close, mobile-safe scrolling, workspace selection and customer-safe network failure messaging. Raw service diagnostics are not shown in the customer interface.

## Canonical database

The permanent populated Neon branch is `lexa-live` (`br-soft-star-b1dj2m2w`) in the `LEXA` project (`wispy-mud-75323042`). It is non-expiring and is the project default branch. The API readiness check verifies the Neon branch identity before allowing the application to report the database as ready.

The legacy empty `production` branch was not modified.

## Validation

44 automated Python tests pass. The visible product contract and frontend hardening contract pass. TSX/TS source files were syntax-checked with TypeScript. CSS compatibility warnings identified in the previous deployment were corrected. A full Next.js production build was not possible in this execution environment because dependency installation did not complete within the available execution window.
