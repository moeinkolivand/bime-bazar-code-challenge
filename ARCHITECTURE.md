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
PENDING
    │
    ├────────► CONFIRMED
    │
    ├────────► CANCELLED
    │
    └────────► EXPIRED
```

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

The reservation workflow depends only on provider capabilities rather than concrete provider implementations.

For example:

- Internal inventory can reserve stock immediately.
- External providers may expose reservation APIs.
- Read-only providers only support availability checks.

This allows new providers to be added without modifying reservation logic.

---

# Reservation Flow

## 1. Create Reservation

When a checkout starts:

1. Validate requested quantities.
2. Lock inventory rows.
3. Verify available stock.
4. Reserve inventory locally.
5. Call provider reservation API if supported.
6. Persist reservation.
7. Return reservation details.

If any step fails, the transaction is rolled back and inventory remains unchanged.

---

## 2. Confirm Reservation

After receiving a successful payment event:

1. Validate reservation status.
2. Confirm provider reservation if required.
3. Consume reserved inventory.
4. Create order.
5. Mark reservation as confirmed.

This ensures inventory is only consumed after successful payment.

---

## 3. Cancel Reservation

Reservations may be cancelled because of:

- payment failure
- user cancellation
- expiration

Cancellation releases reserved inventory and notifies providers if necessary.

---

# Concurrency Strategy

Overselling is one of the biggest risks in reservation systems.

To guarantee correctness, inventory updates occur inside database transactions while locking inventory rows using pessimistic locking (`SELECT ... FOR UPDATE`).

This ensures:

- only one reservation modifies inventory at a time
- concurrent requests wait instead of overselling
- available inventory never becomes negative

Although optimistic locking could provide higher throughput, pessimistic locking was chosen because inventory conflicts are relatively rare compared to the cost of overselling.

Correctness was prioritized over maximum throughput.

---

# Idempotency

Reservation creation supports idempotent requests.

Clients may safely retry requests using an idempotency key without creating duplicate reservations.

This protects against:

- network retries
- client timeouts
- duplicate API submissions

---

# Failure Handling

External providers are considered unreliable.

Provider interactions are isolated behind provider implementations so failures remain localized.

Typical failures include:

- timeout
- network error
- provider rejection

Current implementation demonstrates multiple scenarios:

### Scenario 1

Local reservation succeeds.

Provider reservation succeeds.

Reservation becomes active.

### Scenario 2

Local reservation succeeds.

Provider reservation fails.

The local transaction is rolled back and the reservation is rejected.

This guarantees consistency between local inventory and provider state.

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
- Authentication is already completed.
- Products already exist.
- Provider credentials are preconfigured.
- Reservation expiration time is configurable.
- Inventory quantities cannot become negative.

---

# Trade-offs

Several deliberate trade-offs were made.

## Simplicity over Distributed Consistency

Provider communication is performed synchronously.

For a production-scale system this would likely move to asynchronous messaging using an Outbox pattern, but synchronous communication keeps the implementation easier to understand for the scope of this assignment.

---

## Strong Consistency over Throughput

Inventory updates use pessimistic locking.

This slightly reduces throughput under heavy contention but completely prevents overselling.

Given the business domain, correctness is more important than raw performance.

---

## Extensibility over Premature Abstraction

Provider integrations are abstracted behind interfaces because supporting multiple providers is a core business requirement.

Other areas remain intentionally simple until additional complexity becomes justified.

---

# What I Would Improve With More Time

If this service evolved into a production system, the next improvements would include:

- Outbox Pattern for reliable provider communication
- Retry policies with exponential backoff
- Circuit breakers for unstable providers
- Background worker for expired reservations
- Distributed tracing
- Prometheus metrics
- Audit log for inventory mutations
- Event-driven order creation
- Dead-letter queues for failed provider operations

These additions would improve resilience and scalability while preserving the existing domain model.