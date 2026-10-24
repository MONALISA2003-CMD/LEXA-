# Phase 3 — Uganda tax calculator and manual-only compliance (no paid integrations)

**Reference date:** 24 October 2026  
**Operating rule:** LEXA does not process or move money and does not submit EFRIS documents.

## Product decision

LEXA is a business-recording system only. It records how an owner says a payment was made—cash, mobile money, bank, card, cheque or other—together with the amount, business date, safe optional reference, allocation and accounting evidence. Recording a payment is not a charge, collection, transfer, settlement, or confirmation from a bank/mobile-money operator. No mobile-money/payment-gateway API, merchant provisioning, webhook, credential vault or provider status polling is part of this plan.

LEXA does not connect to URA EFRIS, generate a genuine URA FDN, issue a legal e-invoice, submit fiscal documents, or verify the QR/verification code. The owner uses the official URA process separately and may copy the returned document identifiers into LEXA for bookkeeping. Every new manual fiscal document stays `DRAFT`, with metadata `record_method=MANUAL_URA_PORTAL`, `verification_status=NOT_VERIFIED_BY_LEXA`, and `external_submission=false`. A LEXA sales/payment receipt must never be labelled an official EFRIS receipt.

The API now exposes local, permission-protected estimates and reference data under `/api/v1/compliance/tax-reference` and `/api/v1/compliance/tax-estimate`. They execute in Python/Decimal locally and do not make external network calls. The legacy fiscalise route returns `409 EFRIS_MANUAL_ONLY`; the legacy config endpoint rejects `SYSTEM_TO_SYSTEM` and any non-`MANUAL` mode.

## Implemented local calculations

- **VAT:** 18% standard-rate calculation, both tax-exclusive and tax-inclusive; Decimal arithmetic and rounding. The standard default rule is activated only after an owner confirms the business is registered/obliged to charge standard VAT. It takes effect from 1 July 2026 and is resolved server-side by saved effective-dated product/category/default rules at checkout. Zero-rated and exempt supplies are distinct; a 0% reference is not applied as an automatic default. The owner must select whether saved prices already include tax.
- **Presumptive income tax:** resident eligibility check, annual turnover ceiling of UGX 150 million, records/no-records bands and the published exclusions. LEXA refuses to silently choose a different income-tax regime if facts do not qualify.
- **PAYE:** resident-individual monthly brackets in URA's updated FY 2026/27 notice effective 1 July 2026, plus the separately published non-resident schedule. Payroll deductions and individual circumstances still require review.
- **Withholding tax:** estimate is offered only when the owner confirms the business was appointed as a withholding-tax agent. The cited 6% taxable-supply rule is applied only when the amount exceeds UGX 1 million; professional/management estimate uses 6% for resident and 15% for non-resident payees. Classification, exceptions and statutory base must be checked before a real deduction or filing.
- **Threshold conflict:** URA's 23 October 2026 FAQ says VAT registration is mandatory above UGX 300 million annual taxable turnover, while another official Government of Uganda VAT page says UGX 250 million under the 2026 amendment. LEXA shows both and will not decide VAT-registration status or automatically enable VAT from turnover alone. Confirm the operative requirement with URA before relying on it.

## Official references, cited in-app

- URA, **Ask URA Commissioner General 41**, published 23 October 2026: https://ura.go.ug/en/ask-ura-commissioner-general-41/
- URA, **Changes to PAYE Return Form following the Income Tax (Amendment) Act, 2026**, published 7 September 2026: https://ura.go.ug/en/changes-to-paye-return-form-following-the-income-tax-amendment-act-2026/
- URA, **Additional taxpayers required to use EFRIS**, published 10/11 August 2026: https://ura.go.ug/en/additional-taxpayers-required-to-use-efris/
- URA EFRIS overview and registration guidance: https://ura.go.ug/en/efris/ and https://ura.go.ug/en/efris/efris-registration/
- Government of Uganda, **VAT Registration — Licensing & Compliance**: https://doingbusiness.finance.go.ug/licensing/ura-vat-registration

## Guardrails and release evidence

1. No database migration is required by this overlay; it reuses the existing tax, EFRIS, payment-channel and fiscal-document tables. Do not rerun previously applied production migrations 045–047.
2. Payment channels remain tenant-scoped records. No payment API secrets, account numbers, PINs, OTPs, gateway tokens, callbacks or provider confirmation are stored or called by Phase 3.
3. Manual fiscal documents are tenant-scoped, audited, and never upgraded to accepted/submitted just because a user entered an FDN. The optional sale reference must refer to a completed sale in the same tenant and use matching currency.
4. An owner must review the selected tax treatment, supply class, tax-inclusive price setting, statutory eligibility, and effective dates. Calculators are planning/bookkeeping aids, not a substitute for an official assessment or tax advice.
5. Add a zero-rate/product/category override where appropriate. Never classify all goods as standard-rated simply because the VAT calculator knows the 18% formula.
6. On the exact extracted commit, pass API pytest, the complete web Node contract suite, TypeScript typecheck, Next.js production build, Compose and HAProxy checks. The targeted local test pass is not the same as full CI.
7. Validate the `/ready` response, Render/Vercel source SHA and signed-in tax/payment-recording screens after deployment. EFRIS acceptance evidence must be checked in the official URA portal, outside LEXA.

## Acceptance tests added by this overlay

- Focused local verification: **13 Python tests passed** across the local Uganda tax module and existing transaction-evidence contract; **5 Node tests passed** across Phase 2, Phase 3 and CI regression contracts; Python compilation succeeded for all included changed API modules; TypeScript syntax transpilation of the compliance page returned zero diagnostics.
- Frontend contract checks protect manual-only EFRIS mode, local tax estimation, no provider-call code in the added tax route, and the record-only payment model.
- The complete repository Node suite, full TypeScript typecheck, Next.js production build, live authenticated staging acceptance and post-extraction CI have not been run on this overlay. Require those checks on the new canonical commit before production deployment.
- This package deliberately adds no URA or mobile-money adapter and contains no provider credentials.
