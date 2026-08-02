## Overview

This service is responsible for managing inventory reservations during the checkout flow.

The primary goals of the design are:

- Prevent overselling under concurrent requests.
- Keep inventory consistent throughout the reservation lifecycle.
- Support multiple inventory providers with different capabilities.
- Keep business logic independent from provider-specific implementations.
- Provide a clean foundation for future scalability while keeping the current implementation reasonably simple.

The system is intentionally designed as a modular monolith. Although several components could eventually become independent services, keeping them in one service significantly reduces operational complexity while still enforcing clear domain boundaries.

---

# High-Level Architecture

The application is divided into the following logical modules:

```
                +-------------------+
                | Reservation API   |
                +---------+---------+
                          |
                          v
               Reservation Service
                          |
        +-----------------+----------------+
        |                                  |
        v                                  v
 Inventory Service                Provider Registry
        |                                  |
        |                          +--------+--------+
        |                          |                 |
        |                    Internal Provider   External Providers
        |
        v
      Database
```

Each module has a single responsibility and communicates through well-defined interfaces.

---

# Domain Model

The core domain consists of the following entities:

- Product
- Inventory
- Reservation
- ReservationItem
- Order
- InventoryProvider

Instead of treating inventory as a single quantity, inventory is separated into:

- Available quantity
- Reserved quantity

This makes reservation operations explicit and prevents overselling.

Reservations have their own lifecycle independent from orders.

```
CREATING
    │
    ▼
PENDING_LOCAL
    │
    ▼
PENDING ──────────► CONFIRMING ──────────► CONFIRMED
    │                                          ▲
    ├─────────────► CANCELLED                  │
    │                                    (still reached even if
    └─────────────► EXPIRED               some items FAILED to
                                            confirm — see
                                            Confirm Reservation)
```

Reservation items carry their own finer-grained status independent of the
parent reservation: `HELD_LOCAL → HELD → CONFIRMED / FAILED / RELEASED`.
This lets the system express "local stock reserved, upstream provider call
still pending" as a real, queryable state rather than collapsing it into a
single boolean.

Orders are only created after a reservation has been successfully confirmed.

---

# Inventory Providers

One of the primary design goals was supporting multiple inventory providers with different capabilities.

Different providers may:

- support reservation
- only expose stock availability
- require different authentication
- have different response times
- fail independently

To avoid provider-specific logic leaking into the business layer, the service uses a Provider Registry.

The reservation workflow depends only on provider **capabilities** (`StockCheckable`, `Reservable`) rather than concrete provider implementations. `ProviderRegistry` asserts at first use that a provider's declared `capabilities.can_reserve` flag matches whether its client actually implements `Reservable`, so a misconfigured provider fails loudly at startup instead of silently at call time.

Three provider implementations exist today:

- **Internal** — the platform's own warehouse. Our DB row is already the source of truth, so every method is a trivial local no-op that satisfies the interface uniformly.
- **Warehouse (external, full capability)** — REST-based, implements both `StockCheckable` and `Reservable`: check / reserve / confirm / release.
- **Marketplace Seller X (external, read-only)** — implements `StockCheckable` only. It has no hold/reserve API at all, which has real consistency implications — see **Known Limitations** below.

This allows new providers to be added without modifying reservation logic.

---

# Reservation Flow

## 1. Create Reservation

When a checkout starts:

1. Validate requested quantities.
2. Lock inventory rows.
3. Verify available stock.
4. Reserve inventory locally.
5. Call provider reservation API if the provider supports it (`Reservable`).
6. Persist reservation.
7. Return reservation details.

If any step fails, the transaction is rolled back and inventory remains unchanged.

For providers that are `StockCheckable`-only (no `Reservable`), step 5 today is a no-op — the local hold alone is treated as sufficient at creation time. See **Known Limitations** for why this is a real gap and what mitigates it.

---

## 2. Confirm Reservation

After receiving a successful payment event:

1. Validate reservation status.
2. Confirm provider reservation if the item has a provider reservation reference (`Reservable` providers).
3. For providers with no upstream hold (`StockCheckable`-only), revalidate stock as a last-moment check instead.
4. Consume reserved inventory.
5. Create order.
6. Mark reservation as confirmed.

Importantly: if some items fail to confirm (provider rejects, revalidation shows insufficient stock, etc.), the reservation is still moved to `CONFIRMED` overall — because payment has already been taken by this point — and the caller receives `ReservationConfirmationIncompleteError` to handle the failed items. This is a deliberate choice: rolling the whole reservation back after payment succeeded would mean charging a customer for nothing. Failed items remain in a state (`HELD` or `FAILED`, depending on where they failed) that a reconciliation process can act on.

---

## 3. Cancel Reservation

Reservations may be cancelled because of:

- payment failure
- user cancellation
- expiration

Cancellation releases reserved inventory and notifies providers if necessary. Release failures (local or upstream) are logged and swallowed rather than raised, so one provider failure doesn't block releasing the rest of the items — items that couldn't be released are left in a dangling state for later reconciliation rather than blocking the cancel operation.

---

# Concurrency Strategy

Overselling is one of the biggest risks in reservation systems.

To guarantee correctness, inventory updates occur inside database transactions while locking inventory rows using pessimistic locking (`SELECT ... FOR UPDATE`). The same pattern is used for reservation-level status transitions (`lock_and_transition`), with a `version` counter carried alongside as an audit trail — the row lock, not the version comparison, is what actually prevents concurrent writers from interleaving.

This ensures:

- only one reservation modifies inventory at a time
- concurrent requests wait instead of overselling
- available inventory never becomes negative

Although optimistic locking could provide higher throughput, pessimistic locking was chosen because inventory conflicts are relatively rare compared to the cost of overselling.

Correctness was prioritized over maximum throughput.

---

# Idempotency

Reservation creation supports idempotent requests via a client-supplied `client_idempotency_key`. Clients may safely retry requests using the same key without creating duplicate reservations.

This protects against:

- network retries
- client timeouts
- duplicate API submissions

The uniqueness constraint is scoped per-user, matching `find_by_client_idempotency_key(user_id, key)` — two different users may safely reuse the same key value.

---

# Failure Handling

External providers are considered unreliable. Provider interactions are isolated behind provider implementations so failures remain localized, and are composed from three reusable, generic pieces so each provider only configures parameters, not logic:

- **RetryPolicy** — retries only on timeout (`ProviderRequestError.is_timeout`), with exponential backoff. Non-timeout errors (e.g. explicit rejection) are not retried.
- **CircuitBreaker** — opens after a configurable consecutive-failure threshold, refuses calls during the cooldown window, and probes with a half-open state afterward.
- **CallLogger** — records every provider call (success, timeout, failure) with latency, for later auditing.

Each external provider client configures its own thresholds — e.g. the marketplace provider (known to be slower and less reliable) uses more retries, a longer timeout, and a shorter failure threshold before opening its circuit than the warehouse provider.

Two failure scenarios are implemented and covered by tests:

### Scenario 1 — Provider reservation succeeds

Local reservation succeeds. Provider reservation succeeds. Item becomes `HELD` with a `provider_reservation_ref`. Reservation proceeds to `PENDING`.

### Scenario 2 — Provider reservation fails or times out

Local reservation succeeds. The upstream `reserve_upstream` call fails or raises (timeout, rejection, network error). The local hold is released, the item is marked `FAILED`, and if any item in the reservation fails this way, all previously-held items in the same reservation are released and the reservation is cancelled — reservation creation is all-or-nothing.

### Scenario 3 — Read-only provider stale/insufficient stock at confirm time

For a `StockCheckable`-only provider, confirm-time `revalidate_stock` can come back `False` (the provider no longer has enough stock). The local hold is released, the item is marked `FAILED`, and the reservation still moves to `CONFIRMED` overall (payment was already taken) while the caller is notified via `ReservationConfirmationIncompleteError`. This scenario is also the entry point into the race-window limitation described below.

---

# Testing

`app/modules/reservation/tests/tests.py` contains ~30 unit tests covering the orchestration logic in `ReservationService` and `ReservationItemReserver`. `ReservationRepository` and the inventory port are fully mocked — no database, no network — so the suite runs fast and deterministically, and tests only the *decisions* the service layer makes, not persistence or transport concerns.

**Local hold correctness** — the happy path; a regression test asserting `hold_stock` is called *exactly once* per item (guards against a double-decrement bug); insufficient stock raises and marks the item `FAILED`; an exception from the inventory port is caught and converted into a domain error instead of leaking.

**Upstream reservation outcomes** — provider success marks the item `HELD` with a reference; a `StockCheckable`-only provider's no-op success is still treated as valid `HELD` (Scenario 2); provider failure releases the local hold and marks `FAILED`; a raised exception (simulated timeout) is treated the same as an explicit failure; items not in `HELD_LOCAL` are skipped for idempotent re-entry; the client's idempotency key is correctly threaded through to the provider call.

**Reservation creation as a whole** — all-items-succeed; the specific multi-item rollback case (one item fails, previously-held items are released, not left partially held); duplicate idempotency key returns the existing reservation without redoing work; a local hold failure rolls back the transaction; a simulated DB race on the idempotency-key insert (`IntegrityError`) is handled rather than propagating a raw DB error; empty item lists document current behavior explicitly rather than leaving it unspecified.

**Confirmation** — not-found and not-pending guards; full success consumes stock and marks `CONFIRMED`; a partial failure (one item confirms, one doesn't) still moves the *reservation* to `CONFIRMED` because payment was already taken, while raising an error for the caller to reconcile the failed item — with a dedicated all-items-fail variant proving the same rule holds at the extreme; a read-only provider's revalidation failure at confirm time releases the hold and marks the item `FAILED` (Scenario 3); a version conflict during the `CONFIRMING` transition raises a concurrency error instead of silently overwriting.

**Cancellation and expiry** — releasing held items and upstream refs; skipping items that were never held; not-found handling; cancelling an already-`CONFIRMING` reservation is correctly rejected rather than silently allowed; a version conflict on cancel raises rather than proceeding; the expiry sweep releases stock and upstream refs per reservation, no-ops cleanly when nothing's expired, skips (rather than crashes on) a reservation that changed status concurrently, and correctly processes multiple expired reservations in one sweep; confirming or cancelling an already-`EXPIRED` reservation is rejected with the correct domain error, not a generic one.

**Compensation logic** — releasing a mix of items (some with upstream refs, some without, some already `FAILED`) correctly skips what doesn't need releasing; a release failure on one item doesn't stop the others — the loop continues and marks what it can.

**Input validation** — zero and negative quantities are rejected at the DTO layer before reaching the service.

**Not covered by this suite:** anything requiring a real Postgres connection — so the actual `SELECT ... FOR UPDATE` locking behavior and the (now-fixed) composite idempotency constraint are untested at the integration level — as well as the HTTP route layer and the provider HTTP clients themselves (retry/circuit-breaker timing, real request/response handling). This is a reasonable scope for the assignment's timeframe, but is named here explicitly rather than left for a reviewer to discover by reading 971 lines of test code.

---

# Known Limitations

## Read-only-provider race window (stock check-then-act)

For providers that only support `StockCheckable` (no hold/reserve API — e.g. the marketplace seller), there is no way to get exclusivity over their stock. The only tool available is "ask if there's enough, then act on the answer" — and nothing prevents the real stock from changing in the gap between those two steps, because we don't control that provider's database.

**Current behavior:** the first time stock is checked against a read-only provider is at *confirm* time (`revalidate_stock`), not at reservation-creation time. `ProviderService.reserve()` returns `success=True` immediately for non-`Reservable` clients without calling the provider at all. This means a customer can complete payment before we've ever asked the read-only provider whether stock still exists — the worst possible time to find out it doesn't.

**Recommended next steps (not yet implemented):**

1. **Check stock at creation time too**, not only at confirm. Add a `check_stock()` call for `StockCheckable`-only providers inside `ProviderService.reserve()` before returning success, so an out-of-stock item is rejected immediately at checkout start rather than after payment. This narrows the exposure window from "entire checkout duration" down to "the moment right before confirm," and fails fast for the customer.
2. **Add a safety margin to revalidation.** `revalidate_stock` currently requires `qty_available >= required_quantity` exactly; requiring a configurable buffer (e.g. `required_quantity + margin`) reduces — without eliminating — the chance that a sale happening in the gap causes an actual oversell.
3. **Accept and document the residual risk.** Even with (1) and (2), the gap cannot be fully closed without a hold primitive on the provider's side, which this provider class does not offer by definition. The honest long-term fix is a reconciliation path: if the provider later reports a fulfillment failure (webhook, manual ops report, etc.), that triggers an order-cancellation/refund flow rather than assuming confirm-time revalidation is sufficient on its own.

This is a structural limitation of read-only providers, not an implementation bug — but it should be treated as an accepted, documented risk rather than an implicit one.

---

# Why a Modular Monolith?

The assignment focuses on correctness rather than distributed systems.

Although splitting inventory, orders and providers into separate services is possible, doing so would introduce:

- distributed transactions
- eventual consistency
- message brokers
- operational overhead

A modular monolith provides:

- simpler deployment
- easier debugging
- strong transactional guarantees
- lower complexity

while still maintaining clean module boundaries.

---

# Assumptions

The specification intentionally leaves several implementation details open.

The following assumptions were made:

- Payment processing is external.
- Authentication is already completed (`user_id` is currently passed as a plain request field/query param — in a production system this would come from a verified auth context/header instead).
- Products already exist.
- Provider credentials are preconfigured.
- Reservation expiration time is configurable.
- Inventory quantities cannot become negative.

Several domain-level assumptions carry more reasoning than fits in a bullet list, so they're documented in place instead of repeated here — see **Concurrency Strategy** (why pessimistic locking over optimistic), **Confirm Reservation** (why the reservation still moves to `CONFIRMED` on partial item failure), **Idempotency** (why the uniqueness constraint is scoped per-user rather than globally), and **Known Limitations** (the read-only-provider race window and why it's an accepted risk rather than a bug).

---

# Trade-offs

Several deliberate trade-offs were made.

## Simplicity over Distributed Consistency

Provider communication is performed synchronously.

For a production-scale system this would likely move to asynchronous messaging using an Outbox pattern, but synchronous communication keeps the implementation easier to understand for the scope of this assignment.

---

## Strong Consistency over Throughput

Inventory updates use pessimistic locking.

This slightly reduces throughput under heavy contention but completely prevents overselling for providers that support real holds. It does **not** fully prevent overselling for read-only providers — see Known Limitations.

Given the business domain, correctness is more important than raw performance.

---

## Extensibility over Premature Abstraction

Provider integrations are abstracted behind interfaces because supporting multiple providers is a core business requirement.

Other areas remain intentionally simple until additional complexity becomes justified.

---

# What I Would Improve With More Time

With the resilience layer (retry/circuit breaker/call logging) and the failure-scenario coverage already in place, the next priorities would be:

- Implement creation-time stock checks and a safety margin for read-only providers (see Known Limitations)
- Outbox Pattern for reliable, asynchronous provider communication
- Background worker for expired reservations (currently would need to be triggered externally/via cron rather than running continuously)
- Distributed tracing and Prometheus metrics
- Audit log for inventory mutations
- Event-driven order creation
- Dead-letter queues for failed provider operations

These additions would improve resilience, correctness, and scalability while preserving the existing domain model.