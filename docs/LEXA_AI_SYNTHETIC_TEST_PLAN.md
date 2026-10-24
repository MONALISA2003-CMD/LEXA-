# LEXA central policy: synthetic offline test plan

These fixtures are made-up examples for regression tests. The test suite does not send them to an external model, fetch a provider, or consume credits.

| Scenario | Synthetic example | Required behavior under test |
|---|---|---|
| Kampala kiosk sales | Recorded sales UGX 245,000; cash-payment breakdown missing | Use clear English; preserve UGX; state that the cash breakdown is missing, not zero. |
| Wakiso grocery stock | 12 kg rice and 4 oil bottles recorded; delivery count missing | Do not invent a delivery or make an ungrounded reorder claim. |
| Mbarara salon accounting | Sales UGX 1,200,000; receipts for UGX 85,000 expenses missing | Do not claim profit or VAT can be verified from those numbers alone; recommend checking original records. |
| Jinja hardware receivables | Aggregate receivables UGX 420,000; due dates missing | No invented customer identity or follow-up action; ask for missing information. |
| Provider quota exhaustion | Mock provider returns HTTP 429 | Return a bounded quota/rate-limit error; no retry to another provider and no automatic paid fallback. |
| Provider outage | Mock provider returns HTTP 5xx | Return a generic provider-unavailable error; do not expose the provider response body or retry a different provider. |
| LEXA request limit | Mock Redis bucket is already above the configured per-minute limit | Block with `AI_RATE_LIMITED`; never use live Redis in the test. |
| Privacy-gate bypass | Client attempts to submit `input_safety_checked=true` or a `sensitivity` field | Strict request schema rejects the extra fields; server still sets `input_safety_checked=False` and the route blocks before adapter invocation. |
| Disabled external execution | Provider key/config/model allowlist may be present in a test, but global gate is false by default | No provider is contacted in CI; external execution is reported unavailable/disabled. |

The tests validate request contracts, policy decisions, deterministic guardrail instructions, NULL-preserving aggregates and error handling. They are not a substitute for a reviewed trusted classifier/redaction stage or a live, separately approved model-quality evaluation.
