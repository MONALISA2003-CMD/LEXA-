# LEXA v2.8.0 — Workspace Convergence & Inventory Operations

## Purpose

v2.8.0 takes the v2.7.0 Catalog and Inventory UI foundation into a coherent operational workspace. The release stays within the locked LEXA modular-monolith architecture: Next.js provides the workspace experience, FastAPI remains the application authority, and Neon PostgreSQL remains the authoritative business system of record.

## Workspace contract

The authenticated experience is organized around one shared shell:

- Home — Command Centre
- Sales
- Inventory
- Purchasing
- Customers
- Products
- Finance
- Reports
- Compliance
- AI Intelligence
- Administration
- Settings

The technical Business Engine remains internal infrastructure and is not a user-facing route.

The shell carries:

- LEXA identity;
- business/workspace context;
- authenticated session state;
- global search / Ask LEXA entry;
- notifications/account affordances;
- online state;
- explicit service-unavailable messaging.

A temporary API/database outage is not treated as a sign-out. A real 401 can still redirect to login.

## Command Centre contract

The Home surface answers:

> What is happening in my business right now?

The page is organized as:

1. today's KPIs;
2. needs attention;
3. today's operational work;
4. daily business movement;
5. fast workspace paths.

While authoritative queries are loading, the UI uses explicit loading placeholders rather than displaying fabricated zero values.

## Product contract

Products now expose the operational commercial identity needed before downstream Sales/Purchasing work:

```text
Product
  ├─ category / brand / description
  └─ Variant
      ├─ SKU
      ├─ barcode(s)
      ├─ costing policy
      ├─ price list price(s)
      └─ inventory visibility
```

Variant activation/deactivation, barcode creation, price-list creation, effective-dated price creation and product/variant inventory visibility are surfaced through the workspace.

Critical catalog mutations use `Idempotency-Key` where the backend contract supports mutation replay safety.

## Inventory contract

Inventory exposes six operational surfaces:

```text
Stock
Ledger
Adjustments
Counts
Transfers
Locations
```

### Adjustments

```text
Draft → Approved → Posted
```

### Stock counts

```text
Counting → Submitted → Approved → Posted
```

### Transfers

```text
Draft → Approved → Dispatched → Received → Completed
```

### Locations

Warehouses group operational locations. Locations are the stock positions used by balances, transfers and counts. Warehouse and location creation are transactionally protected by idempotency, audit and domain-event persistence.

## Business-truth boundary

The frontend never becomes authoritative for inventory, money, accounting, permissions or transaction state.

The authoritative pattern remains:

```text
User action
   ↓
Next.js workspace
   ↓
FastAPI command
   ↓
authorization + validation
   ↓
Neon PostgreSQL transaction
   ↓
audit + durable event/outbox state
   ↓
authoritative response
   ↓
UI refresh / invalidate
```

Redis, AI and realtime are not alternate sources of business truth.

## Search contract

The global shell provides a lightweight command/search surface with a Ctrl/⌘+K shortcut. Query intent is routed to an appropriate workspace rather than directly mutating business data.

Examples:

- inventory / stock / warehouse / transfer / count → Inventory
- product / SKU / barcode / catalog → Products
- sale / POS / invoice / customer / payment → Sales
- purchase / supplier / receiving → Purchasing
- finance / journal / expense / accounting → Finance
- otherwise → Reports

This is a navigation aid, not an AI execution path.

## Failure-state contract

The release distinguishes:

- signed out;
- temporary service/API unavailability;
- validation failure;
- permission/API errors;
- loading;
- empty data.

Transaction screens do not claim completion before an authoritative API response.

## Validation

Required repository gates for v2.8.0:

```text
python -m pytest -q
python -m compileall -q apps/api/app
node apps/web/tests/visible-product-contract.test.mjs
bash scripts/verify-phase3.sh
```

Current result:

- 96 Python tests passed;
- backend compilation passed;
- visible product/frontend hardening contracts passed;
- TypeScript/TSX syntax transpilation passed for all 25 frontend TypeScript/TSX files in the package;
- workspace convergence verification passed.

A dependency-backed full Next.js typecheck/build was not re-run in the local container because the dependency install timed out, and Vercel sandbox creation was denied by the current integration permissions. This release therefore does not claim a fresh full `next build` result.

## Explicit next boundary

The next substantive vertical is Purchasing:

```text
Suppliers
  ↓
Purchase Orders
  ↓
Receiving
  ↓
Partial Receipt
  ↓
Inventory Posting
  ↓
Purchase Returns
```

Sales/POS follows with deterministic payment, receivable and inventory effects.
