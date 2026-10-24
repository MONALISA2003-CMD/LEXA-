# LEXA Product-Language Inventory

**Date:** 24 October 2026
**Approved direction:** Professional and approachable; plain English; technical AI configuration private; unavailable assistant remains useful and truthful.

This inventory distinguishes copy actually changed by this overlay from the wider module-by-module review standard. The source wording in the rows below is the current copy pattern identified during inspection; replacement text is intended as the product standard.

## Applied in this overlay

| Area | Change applied | Validation focus |
| --- | --- | --- |
| Navigation and search | Labels simplified for Checkout, Money & records, Daily overview, Sales forecast, Business assistant, Tax and receipts, Business details, Team access, and Finish setup. Search still resolves established terms and routes. | Keep route paths unchanged; verify links and plain-language search destinations. |
| Business assistant | Removed provider-list requests, provider selector, the question form, provider-specific disclosures, model/pricing/quota copy, and key-handling instructions from the customer-facing page. | Assistant unavailable state is explicit and contains links to existing business tools. |
| Daily overview | Removed references to deterministic rules and external AI; simplified data-quality and empty-state copy; changed technical refresh wording to “Last updated.” | Missing information is never shown as zero; business data and write behavior are unchanged. |
| Sales forecast | Replaced predictive-model terminology and abbreviations with plain descriptions; hid internal table names and implementation status; simplified history requirements and limitations. | Forecast computation, source data, coverage gates, and read-only behavior are unchanged. |
| Documents and review | Replaced internal processing terminology, branch-scoped storage phrasing, and technical method names; simplified currency labels and error messages; clarified that details must be checked against the original. | Human review remains required; no invoice, payment, expense, or accounting record is created by document review. |
| Related API messages | Improved user-facing errors for document review, daily overview, and sales forecast; changed user-visible extraction and forecast limitation messages. | Error messages must not claim success or reveal raw technical details. The focused overlay suite passes. |
| Tests | Updated language contracts and added checks for assistant privacy, availability messaging, route labels, and plain-language forecast/document screens. | Existing behavior and route contracts remain intact. |

## Whole-interface inventory and wording direction

| Module / shared state | Inventory target | Standard wording direction |
| --- | --- | --- |
| Home and dashboard | Page title, date range, summary cards, empty states, indicators | “Business overview,” “Today's sales,” “Amount due,” “Last updated.” Keep zero separate from missing data. |
| Sales and sales history | Sale entry, totals, refunds, status, search, validation | “Record a sale,” “Payment recorded,” “Amount due,” “View sale.” Distinguish sale completion from payment completion. |
| Stock and products | Counts, transfers, adjustments, low-stock state, product identifiers | “In stock,” “Low stock,” “Stock location,” “Product code.” Explain what needs checking. |
| Checkout and daily close | Cart, tender/payment, closeout, duplicate submit, authorization | “Checkout,” “Record payment,” “Finish day.” Never say the sale was completed before the server confirms it. |
| Customers and balances | Customer setup, payment history, credit, overdue status | “Customer,” “Amount due,” “Overdue.” Preserve paid/outstanding distinctions. |
| Purchases and suppliers | Orders, delivery/receiving, supplier bills and payments | Distinguish placing an order, receiving goods, recording a bill, and paying the supplier. |
| Money and accounting records | Payment matching, cash, expenses, journal entries, tax | Explain differences in amounts and review steps; do not alter accounting meaning. |
| Documents | Upload, document types, review, warnings, extracted details | “Details found,” “Check the original,” “Confirm checked details.” A found value is not a verified record. |
| Daily overview and insights | Warnings, recommendations, freshness, missing data | “What to check first,” “Information to check,” “Last updated.” Mark estimates and uncertainty clearly. |
| Sales forecast | History, expected demand, forecast quality, unavailable cases | “Expected units,” “Average forecast error,” “Not enough recent sales history.” A forecast is never a guarantee. |
| Business assistant | Unavailable and available states, safety information | No provider setup, keys, quotas, pricing, or model identifiers in customer screens. Unavailable means no answer is generated. |
| Tax and receipts | Tax settings, official receipt states, business identity | Keep VAT and official document terms where required; explain unfamiliar terms without inventing tax advice. |
| Business details and setup | Profile, currency, branches, required setup, progress | State the exact missing detail: “Add your business name and currency to continue.” |
| Team access | Invite, roles, permissions, member state | Say who has access and what action is permitted. Never reveal internal authorization identifiers. |
| Settings and workspace | Business switching, preferences, security, sessions | Use “Switch business,” “Settings,” and “Sign-in and security.” Explain access issues in user terms. |
| Reports | Filters, periods, empty results, unavailable data | State the reporting period; distinguish no activity from unavailable information. |
| Team chat | Messages, room status, posting errors | Keep actions direct; distinguish a saved message from a failed or pending send. |
| Shared application shell | Search, navigation, setup alert, account menu, page status | Use one term per feature; state exactly what is missing and link to the right setup step. |
| Forms and notifications | Required fields, success/failure, destructive confirmation | Say what to enter, what happened, and what the next step is. Avoid generic success messages when a request failed. |

## Explicitly excluded from customer-facing screens

- Provider and model names for AI services.
- API keys, environment-variable names, endpoint names, configuration flags, and server setup instructions.
- Free/trial quota language, provider rate-limit details, pricing tiers, or paid-service selection.
- Internal database table names, raw response codes, technical extraction method identifiers, and raw server diagnostics.

Necessary operation details may remain in server configuration and private operational documentation. This overlay does not change credentials, provider configuration, deployment settings, database writes, permissions, or business rules.

## Scope note

This bundle applies the wording changes in the “Applied in this overlay” table and includes the whole-interface inventory as the shared review standard. It does not claim that every literal string in every unbundled screen has already been reviewed; the remaining route-specific copy should be checked against this inventory during subsequent code reviews. No business feature phase is advanced by this language work.
