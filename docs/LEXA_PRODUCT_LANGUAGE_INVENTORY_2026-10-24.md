# LEXA Product Language Audit — Full Frontend

**Audience:** Small-business owners, managers and staff in Uganda  
**Writing style:** Plain, professional, helpful English  
**Currency and date context:** Keep Uganda's UGX and local date conventions where they are already supported by the product.

## Shared screen language

| Area | Use this wording | Avoid showing customers |
| --- | --- | --- |
| Business navigation | Business details, Team access, Switch business | Workspace configuration, role/permission configuration |
| Home page | Business overview, Today's priorities, Needs your attention | Internal health states or system status names |
| Stock | Stock levels, Stock history, Stock checks, Restock suggestions | Inventory subsystem, ledger in everyday stock tasks, replenishment |
| Products | Products, Product options, Product codes, Barcodes, Prices | Catalog implementation wording or unexplained SKU jargon |
| Sales and checkout | Sales, Payments received, Past sales, Ways customers pay, End-of-day payment check | Point-of-sale abbreviations without explanation |
| Customers | Customer balances, Amounts customers still owe, Past sales | Receivables where a familiar explanation works |
| Purchases | Purchases and suppliers, Record deliveries, Supplier bills and payments, Amounts due | Payables, unlinked receipt/variance jargon without explanation |
| Money and records | Money reports, Expenses, Money received, Money spent, Recorded, Difference to check | Internal posting states and unexplained accounting system language |
| Tax and receipts | Tax, VAT, Official tax documents, EFRIS (explained in context) | Unexplained fiscal/compliance labels or a claim that URA has approved something when it has not |
| Daily overview | What to check first, Business updates, Information to check | Data-quality anomaly, indicators without context |
| Sales planning | Sales forecast, Estimated units to sell, Past sales range, For planning only | Predictive intelligence, rolling-origin holdout, unexplained WAPE/MAE |
| Documents | Invoices and receipts, Details found in the document, Check every detail against the original | Candidate extraction fields, OCR method names |
| Team messages | Team messages, Conversation, Sign out this device | Thread internals, session revocation |
| Sign-in and setup | Sign in, Reset password, Finish business setup, First business location | Tokens, session identifiers, tenant configuration |
| Errors and empty states | What happened, what was saved if known, and what to do next | Stack traces, table names, HTTP codes, route names, internal error codes |

## Module-by-module scope

The applied wording pass covers these active screens and shared pieces:

1. Home and business overview.
2. Sales, checkout, payment methods, returns and past sales.
3. Stock levels, history, counts, corrections, transfers, locations, stock checks and restocking.
4. Products, options, codes, barcodes and prices.
5. Customer details, balances and past sales.
6. Purchases, suppliers, orders, deliveries, supplier bills, payments and balances.
7. Money records, expenses, customer amounts due, payment checks and reports.
8. Business details, branches, stock locations and setup.
9. Team members, team access and invitations.
10. Tax, VAT, EFRIS and official tax documents.
11. Daily overview, business insights and sales planning.
12. Documents and human review of document details.
13. Business assistant unavailable page.
14. Sign-in, registration, password recovery, invitation acceptance and business switching.
15. Team messages.
16. Shared navigation, search suggestions, loading/empty/error notices, form messages and action buttons.
17. Shared API error copy that reaches the browser.

## Language rules

- Write for business owners and staff who are not software specialists.
- Prefer short sentences, familiar verbs and specific next steps.
- Use one name for each action throughout navigation, headings, buttons, help, empty states and confirmation messages.
- Keep essential accounting and tax meaning accurate. Do not make “invoice” and “receipt” interchangeable, or change the meaning of a payment, refund, tax document or stock movement.
- A forecast is an estimate, not a promise. Explain uncertainty in ordinary words and do not make a recommendation sound like an automatic purchase.
- Distinguish a confirmed zero from a missing figure or an unsuccessful request.
- Never say an action succeeded unless the application confirms it. Say what is known about saved records and offer a safe next step.
- Never show provider names, model names, keys, quotas, pricing or configuration details in ordinary business screens.
- Do not enable the paused assistant as part of a wording change.

## Scope boundaries

Only visible wording, navigation labels, empty/loading/error/help copy and their language-focused contract tests are changed by the language pass. Accounting calculations, posting behaviour, tax rules, APIs, permissions, data access, secrets, provider settings and database schema are not redefined by these text changes.
