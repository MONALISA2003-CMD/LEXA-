# LEXA Product Language Standards

**Status:** Approved baseline for the product-language overhaul
**Tone:** Professional and approachable
**Audience:** Owners, managers, and staff at small and medium businesses, including users who are not software specialists

## Product voice

LEXA should sound like a capable business partner: clear, calm, practical, respectful, and honest about what it has and has not done.

### Core rules

1. **Lead with the user's task.** Prefer “Record a payment” to internal descriptions of the operation.
2. **Use familiar English.** Keep sentences short, explain unfamiliar business terms when they first matter, and prefer concrete verbs.
3. **Use consistent names.** One concept should have one name across navigation, headings, buttons, help text, empty states, and notifications.
4. **Describe the business outcome, not the technology.** Do not expose AI provider names, model names, API keys, configuration flags, service endpoints, request limits, free or trial quotas, pricing tiers, or paid-service choices in customer-facing screens.
5. **Keep configuration private.** Provider settings and secrets belong on the server. Necessary operational details belong only in private operations documentation or appropriately restricted operational tools—not in normal business screens.
6. **Be honest about status.** Clearly distinguish completed, pending, unavailable, failed, and not-yet-set-up actions. Do not imply that an answer was generated, a record was saved, or a task succeeded when it was not.
7. **Explain the next step.** When something is missing or cannot be completed, say what the user can do next when that is known.
8. **Protect business meaning.** Simpler language must not change the meaning of invoices, receipts, taxes, payments, refunds, balances, stock movements, permissions, or accounting records.
9. **Do not turn missing information into zero.** An empty report, failed request, stale summary, and a confirmed zero are different states.
10. **Design for small screens.** Use short labels, clear actions, readable status text, and responsive layouts. Keep focus states and accessible names understandable.

## Word choices

| Prefer | Avoid in customer-facing copy | Notes |
| --- | --- | --- |
| Business assistant | AI provider / model selector | The assistant page must never imply that replies are available when they are not. |
| Sales forecast / expected demand | Predictive intelligence / rolling-origin baseline | A forecast is an estimate, not a promise. Explain its limitations. |
| Stock / stock location | Inventory subsystem / warehouse scope | Use “inventory” where a formal accounting or reporting context needs it. |
| Amount due | Receivable balance, where plain English is enough | Preserve whether an amount is due, overdue, disputed, or already paid. |
| Check that recorded payments match the actual amounts | Reconciliation variance | Keep the formal term when it is legally or operationally necessary, but explain it. |
| Information to check | Data-quality anomaly | Tell the user what needs checking. |
| Details found in the document | Candidate extraction fields | Found details are not confirmed until a person checks them. |
| Update / refresh | Revalidate stale analytics | Use the action the user actually needs to take. |
| Business details | Tenant configuration | Avoid multi-tenant software language in normal screens. |
| Team access | Role/permission configuration | Explain who can do what and how to request access. |
| Tax / VAT | Internal tax category identifier | Keep legally meaningful terms and do not invent tax advice. |
| Invoice / receipt | Treating these as synonyms | These documents serve different purposes and must remain distinct. |

## Error and status messages

- Name the affected task or record when known.
- State whether the requested action succeeded, failed, or is still pending.
- Offer a recovery step when it is safe and supported.
- Do not echo raw server diagnostics, stack traces, internal codes, table names, endpoint names, or configuration identifiers to users.
- Use “No records found for this period” only when a search completed successfully. If the request failed, say that the information could not be loaded.
- Use “The assistant isn't available right now” for an unavailable assistant. Do not invite the user to choose a provider or enter a key, and do not show a question form that implies an answer will be generated.

## Assistant unavailable state

When the assistant cannot respond, keep a useful page with direct links to available business tools such as sales, stock, reports, purchases, customers, and documents. State plainly that the assistant is unavailable and will not generate an answer on that page. Do not display an AI provider list, provider names, model names, keys, quotas, free/trial limits, pricing, or technical setup instructions.

## Review checklist for every screen

- Is the page title understandable without specialist software knowledge?
- Do the navigation label, page title, search suggestions, and buttons use the same name for the feature?
- Are field labels concrete? Does field help explain what to enter?
- Are loading, empty, unavailable, and error states distinct and truthful?
- Are actions and outcomes easy to tell apart?
- Could the wording accidentally claim a financial, tax, stock, or permission change that did not happen?
- Is any provider, model, key, quota, pricing, endpoint, internal identifier, or server configuration exposed?
- Does the layout remain readable and usable on mobile?
