# LEXA Phase 0–2 UI/UX Research and Improvement Plan

**Research date:** 20 October 2026  
**Product:** LEXA business operating workspace  
**Scope:** Sign-in/workspace entry, command centre, business data tables, feedback/loading/error states, responsive behavior, keyboard and touch accessibility. This is a focused source and interface audit, not evidence of user interviews or a complete WCAG conformance evaluation.

## Executive read

LEXA's current visual direction—a restrained navy operations shell with light surfaces, status color and clear business metrics—is appropriate for a business system. It should be refined, not replaced by an unrelated, highly decorative style. The biggest product-quality gains are reliability and comprehension: keep unavailable values distinct from zero, make the active business date explicit, keep tenant and session context clear, make failures recoverable, and ensure search/filter/table interactions are consistent across routes. The live sign-in page is reachable and its form controls have meaningful labels, but the source has a tablet breakpoint risk: a split marketing/form composition can squeeze both columns at intermediate widths. The source candidate now stacks the sign-in sections at 601–800 CSS px and improves keyboard focus and touch target sizing. This improvement still requires a real-browser viewport review before it can be called visually accepted.

## Current-source observations

- The sign-in flow labels email and password fields, uses username/current-password autocomplete, supports password reveal, handles a multi-workspace selection response, and shows a recoverable error banner.
- The shell checks backend readiness and validates/restores the session before presenting protected business information.
- Command Centre panels now independently represent loading, error/unavailable and empty/success cases; data failures should not silently turn into zero values.
- Product search and inventory filters have stale-request handling and test coverage to prevent late results replacing current results.
- The API proxy forwards authorization, cookies, request IDs and idempotency keys, and the local candidate sets no-store and `nosniff` headers.
- The browser-based UX capture did not establish a reliable actual 390 px viewport. Its returned browser remained 1920 px wide even while reporting a simulated overflow result, so that result is not treated as valid evidence of current live mobile overflow.

## Ranked improvements

### P0 — trustworthy business state and security

1. **Show the data's temporal context.** Label the API-selected tenant business date explicitly and avoid allowing the browser's UTC conversion to roll a local date into the prior/next day. Dashboard defaults now delegate the business date to `public.lexa_business_date(now(), tenant_id)`; user-editable date fields still use the browser's local calendar until the user's tenant timezone is surfaced in the session/config contract.
2. **Never imply successful data loading when it failed.** Keep loading, empty, forbidden, unavailable and success states separate; retain retry actions where safe; avoid showing previous data as current when filters change.
3. **Make session/workspace state unmistakable.** Provide a clear, stable workspace identity after authentication; if the session has expired or context is invalid, block protected data and explain the next action without dumping a technical exception.
4. **Treat proxy/API responses as private.** Authenticated and tenant-scoped responses must not be cached by shared intermediaries. Preserve safe correlation identifiers, and do not leak upstream stack traces or secrets.

### P1 — responsive operational layout

1. **Use the same responsive rules across routes.** At 320–600 px use a single-column form/content flow, preserve readable labels and actions, and allow tables to transform into mobile rows/cards or a clearly labeled horizontally scrollable region where two-dimensional comparison is truly necessary. Do not let the entire page become horizontally scrollable merely because a marketing column is too wide.
2. **Keep a calm visual hierarchy.** Use navy for structural/navigation hierarchy, restrained blue for interactive emphasis, semantic green/amber/red for verified statuses, and neutral backgrounds for most surfaces. Reserve high-emphasis callouts for actionable exceptions only.
3. **Make tables task-oriented.** Put the primary action, search, common filters and display controls in a predictable toolbar; label sortable headers; keep keyboard focus and `aria-sort` in sync; disclose secondary row detail progressively rather than cramming every attribute into the initial row.
4. **Scale operations, not decoration.** Prefer alignment, spacing, readable typography and restrained card borders over repeated gradients, excessive shadows and too many colored cards. Business dashboards should prioritize scan speed and clear comparisons over novelty.

### P1 — interaction and accessibility

- Maintain a visible focus indicator with adequate contrast, prevent focus from being entirely obscured by sticky panels/menus, and ensure the focused item remains visible as the user moves through the UI.
- Make high-frequency touch controls comfortably operable. LEXA's candidate sets auth password reveal to at least 44 px high; WCAG 2.2 AA's target-size minimum is 24×24 CSS px subject to stated exceptions, so 44 px is a design comfort target, not the legal minimum.
- Preserve native labels, required states, inline validation references, understandable error text and keyboard operation. Tables should sort with keyboard activation and identify the active sort direction.
- Respect reduced-motion settings. Use skeletons only while loading, not as stand-ins for actual values.

## Candidate changes in this increment

- Added the 601–800 px stacked sign-in layout to prevent narrow two-column squeezing.
- Added an explicit visible keyboard focus style for sign-in controls and kept the password-reveal target at 44 px.
- Added automated source contracts for responsiveness, focus, proxy no-store/security headers, safe return navigation and date selection.
- Added local-calendar date helpers and made Command Centre/dashboard defaults use the tenant business calendar from the API.
- Added a `safeReturnPath` helper that rejects protocol-relative and normalized external destinations.

## Acceptance test matrix

The following is the required matrix; it is **not yet a completed manual/browser result**.

| Viewport | Primary checks |
|---|---|
| 320×720 | No page-level horizontal scrolling; sign-in controls remain visible and operable |
| 360×800 | Labels and long errors wrap; submit control remains reachable |
| 390×844 | Form spacing, password reveal and keyboard focus remain clear |
| 430×932 | Content density stays calm; no empty, oversized panel caused by width change |
| 600×900 | Single-column mobile breakpoint remains stable |
| 601×900 | Tablet layout changes without abrupt overflow |
| 768×1024 | Story panel and form stack with no squeezed columns |
| 800×1000 | Tablet breakpoint edge remains stable |
| 1280×900 | Desktop sign-in and app shell balance; primary action is discoverable |

On an authenticated test tenant, also verify loading/success/empty/401/403/validation/5xx/network failure states; keyboard-only sign-in; workspace selection; session expiration; table sort/filter; and mobile navigation. Do not use production writes to simulate acceptance.

## Sources and how they were used

- [W3C WCAG 2.2 — Target Size (Minimum), SC 2.5.8](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum): normative accessibility benchmark for interactive target size and its exceptions. A 44 px control height here is a product design choice above that minimum.
- [W3C WCAG 2.2 — Focus Not Obscured (Minimum), SC 2.4.11](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum): focus must not be entirely hidden by author-created content.
- [W3C — What's New in WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/): accessibility criteria relevant to focus and pointer targets.
- [IBM Carbon data-table guidelines](https://www.carbondesignsystem.com/building-blocks/core/components/data-table/guidelines/): modern enterprise-table conventions—toolbar for primary actions/search/filtering, sorting, progressive row expansion and batch actions.
- [IBM Carbon data-table accessibility](https://www.carbondesignsystem.com/building-blocks/core/components/data-table/accessibility/): keyboard-sorted headers, focus treatment and programmatic sort announcements.
- [GitHub secure workflow guidance](https://docs.github.com/en/actions/reference/security/secure-use): reviewed use of minimal permissions and full-length SHA pinning for actions; relevant to deployment/release trust, not visual design.

## Confidence and limits

The source observations are high confidence for the inspected repository version. The patterns above are research-informed recommendations from W3C and Carbon documentation. No live user analytics, interviews, support tickets, or customer usability sessions were available in this pass. Do not claim the app conforms to WCAG or passes all responsive viewports until automated plus manual tests are recorded against a real rendered build.
