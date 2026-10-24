# Phase 3 — real Uganda fiscalisation and payment integration gates

## URA EFRIS system-to-system

1. Confirm taxpayer eligibility, TIN/branch mapping, EFRIS registration state and the system-to-system onboarding route with URA.
2. Obtain the current authoritative API specification, credentials/certificates and test endpoint through URA's supported integration process. Do not rely on a community sample as the production contract.
3. Implement a server-only adapter with request signing/encryption exactly as specified by URA; persist correlation/reference IDs; safely retry by idempotency; query/accept only URA authoritative status; redact credentials and payloads from logs.
4. Map each completed eligible sale to the appropriate invoice/receipt type and approved tax mapping. Handle cancellation/returns with credit/debit note flows; preserve original/reversal links.
5. Persist only FDN, verification code, QR information and acceptance/rejection values returned by URA. A queued outbox task is not an accepted fiscal document.
6. Pass URA test cases for accepted/rejected invoices, duplicate keys, timeout and status recovery, credit notes, amounts/tax rounding, connectivity outage and reconciliation before production enablement.

Official public references: https://ura.go.ug/en/efris/ ; https://ura.go.ug/en/efris-handbook/ ; https://ura.go.ug/en/efris-brochure-23-24/ . These pages describe the supported system-to-system path but do not supply this tenant's live credentials or prove approval.

## Named mobile-money integration (MTN MoMo is the first candidate; production choice requires confirmation)

1. Register the LEXA merchant/partner through the official MTN MoMo developer portal and obtain sandbox collection product subscription, current User ID/Credential Token and subscription key in secret manager.
2. Confirm the account is on the current Uganda platform and use the base URL and mandatory `X-Target-Environment` specified in that partner account's documentation. The public migration note lists `https://momoapi.momo.africa` and Uganda target environment `mtnuganda`; re-check for the registered partner before connecting.
3. Implement `RequestToPay` with a stable client transaction reference and idempotency, return pending to UI until provider confirmation, then poll/consume authenticated callback and verify final status.
4. Authenticate callbacks as the current official contract prescribes, reject replay/invalid signatures, compare amount/currency/merchant reference, deduplicate notifications, and persist provider transaction IDs and status evidence. Never mark “paid” from a browser redirect alone.
5. Add refunds/disbursements only after separately authorized product registration; use signed audit trail, reconciliation, retries and reversal-safe accounting. Manual payments remain marked “recorded by staff” rather than provider-verified.
6. Test pending/success/failure/unknown, delayed callback, duplicate callback, mismatched amount/currency, timeout then status recovery, provider outage, refund, and daily merchant settlement reconciliation in sandbox.

Official public references: https://www.mtn.co.ug/helppersonal/mtn-open-api/ ; https://momo.mtn.com/api/ ; https://momodevelopercommunity.mtn.com/product-updates .

## Release rule

Do not turn on live EFRIS or payment collection until real credentials and account setup have been supplied through approved secret management, sandbox tests pass, legal/tax setup is reviewed, and the release is explicitly approved. No FDN, verification code, QR, provider transaction status or successful payout is to be fabricated.
