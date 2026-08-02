## Overview

The current implementation is designed to prioritize **correctness**, **consistency**, and **maintainability** over extreme scalability.

Inventory reservation is a business-critical operation where overselling is unacceptable. Therefore, several design decisions intentionally favor strong consistency even if they reduce maximum throughput.

The architecture is suitable for a medium-sized e-commerce platform and provides clear evolution paths as traffic increases.

---

# Current Scalability Characteristics

The service scales well for:

- Multiple application instances
- Moderate inventory contention
- Multiple inventory providers
- Thousands of concurrent checkout sessions

The application itself is stateless, allowing horizontal scaling by simply adding more application instances behind a load balancer.

The primary shared state resides in the database.

---

# Primary Bottlenecks

As traffic grows, several bottlenecks will appear before the application servers become the limiting factor.

## 1. Database Contention

The first scalability bottleneck is inventory updates.

Each reservation acquires a pessimistic lock on inventory rows.

Under heavy demand for popular products:

```
User A
    │
    ▼
Locks Inventory Row
    │
User B waits
    │
User C waits
    │
User D waits
```

This reduces throughput for highly contested inventory.

### Why this trade-off?

Overselling inventory is more expensive than temporarily reducing throughput.

The system deliberately favors correctness over maximum concurrency.

---

## 2. Synchronous Provider Calls

Reservation creation currently communicates directly with external inventory providers.

Slow providers increase API latency.

```
Reservation Request

↓

Local Reservation

↓

External Provider

↓

Client Response
```

A provider timeout directly impacts checkout response time.

**A sharper version of this problem shows up in `confirm_reservation` specifically.** Each item is confirmed inside its own savepoint (`reservation_repo.transaction()`), but savepoints don't release the outer transaction's row locks — those are only released when the whole request's DB transaction commits, at the very end of the method. So if a reservation has multiple items, and item 1's `consume_stock` has already acquired a `SELECT ... FOR UPDATE` lock on its inventory row, that lock stays held while item 2's `confirm_upstream` makes a synchronous network call to an external provider (up to several seconds with retries). A slow provider on item *N* extends the DB lock hold time on items *1* through *N-1*, not just its own request latency. Under load, this turns "provider is slow" into "provider is slow **and** it's now blocking unrelated requests waiting on those earlier inventory rows" — this is the concrete mechanism connecting provider latency to database contention (bottleneck #1), not just checkout response time in isolation.

---

## 3. Reservation Expiration

Expired reservations eventually accumulate.

As reservation volume grows, expiration processing becomes increasingly expensive.

Without periodic cleanup:

- reserved inventory remains locked
- database tables grow continuously
- queries become slower

**A specific, currently-real version of this:** `find_expired_and_lock` has no `LIMIT` — it locks (`FOR UPDATE SKIP LOCKED`) and returns *every* expired reservation in one query, then `expire_reservations` processes all of them, one by one, within that single worker tick. Under normal conditions (a steady trickle of abandoned carts) this is invisible. It stops being invisible the moment expired volume spikes — the worker being down for a while, a flash sale with high abandonment, or simply reservation volume growing past what one 30-second tick can process. At that point one tick locks a large, unbounded number of inventory rows and holds them for however long it takes to process the whole batch sequentially, which is exactly the kind of long-held-lock event bottleneck #1 (Database Contention) already flags as the most expensive failure mode in this system — except here it's self-inflicted by the maintenance job rather than caused by user traffic.

The fix is straightforward: add a `LIMIT` (e.g. 100–500) to `find_expired_and_lock`, and have `expire_reservations` loop — process one batch, commit, fetch the next batch — until a fetch returns fewer rows than the limit. This bounds both the lock hold time and the worker tick duration regardless of how large the expired backlog gets, at the cost of a few extra round trips when the backlog is large. Not implemented today; worth doing before this job runs against production-scale abandoned-cart volume.

---

## 4. Database Growth

Several tables continuously grow:

- Reservations
- Reservation Items
- Orders
- Provider Call Logs — the schema and repository (`ProviderCallLogRepository`, `provider_call_logs` table) already exist, but `CallLogger` is not currently wired into the provider clients (`WarehouseProviderClient`, `MarketplaceSellerXProviderClient` call the transport directly). So this table doesn't grow *yet* — but the moment it's wired in (which it should be — see Observability below), it will grow at least as fast as reservations, since every provider call, not just every reservation, produces a row.

Historical reservation data is valuable for auditing but increases storage and query costs over time.

---

## 5. Per-Instance Resilience State

Retry and circuit-breaker logic (`RetryPolicy`, `CircuitBreaker`) are already implemented and, after the recent fix to `get_provider_registry` (caching it via `lru_cache` instead of constructing it per-request), their state now correctly persists for the lifetime of one process.

That fix does not extend to multiple processes. Under Stage 1 horizontal scaling, each app instance gets its **own** cached `ProviderRegistry`, and therefore its own independent `CircuitBreaker` state per provider. Two concrete consequences as instance count grows:

- **Diluted failure detection.** A breaker opens after `failure_threshold` (e.g. 5) consecutive failures *on that instance*. With N instances splitting traffic round-robin, a provider that's failing 100% of the time still takes roughly N× longer to trip circuit-wide than it would on a single instance, because each instance is independently counting from zero.
- **Thundering-herd re-probing.** When the cooldown window elapses, every instance transitions to `HALF_OPEN` and re-probes independently, at roughly the same time (since they likely opened around the same time). A provider that's recovering slowly gets hit by N simultaneous probes instead of one, which can be enough to knock it back down — defeating the point of the half-open state.

This only matters once you're actually running multiple instances (Stage 1) with a provider under real, sustained failure — at low traffic or single-instance deployments it's a non-issue. The fix, when it's needed, is to move breaker state out of process memory and into something shared — Redis is the natural choice since it's already in this codebase (currently used for OTP storage), and a simple shared counter + TTL-based open/cooldown flag per provider is enough; it doesn't need the full breaker logic to live in Redis, just the state.

**Also worth noting while this code path is fresh:** `CircuitBreaker`'s state mutation isn't behind a lock. FastAPI runs sync route handlers in a thread pool, so two concurrent requests hitting the same provider on the same instance can race on `_failure_count` — this is a narrow, low-severity race (worst case: an undercounted failure, not a crash or an incorrect open/close decision that sticks), but worth a `threading.Lock` around `CircuitBreaker.execute` if this is taken further.

---

## 6. ORM Query Pattern (N+1 risk)

`Reservation.items` is a lazily-loaded relationship. `confirm_reservation`, `cancel_reservation`, and `expire_reservations` all iterate `reservation.items`, which triggers a separate query per reservation the first time `.items` is accessed (an N+1 pattern) unless the initiating query already eager-loaded it. `find_expired_and_lock` in particular processes a batch of reservations in a loop — at low expiry volume this is invisible, but as the platform grows and abandoned-cart volume grows with it, this becomes a query-count multiplier on exactly the code path (Stage 2's background worker) that's supposed to be lightweight, periodic maintenance work. Fix is a one-line `selectinload(Reservation.items)` on the relevant queries in `ReservationRepository` — cheap to do, easy to forget until a profiler catches it.

---

# Scaling Strategy

Rather than redesigning the system immediately, the architecture supports incremental improvements.

---

# Stage 1 — Horizontal API Scaling

The application is stateless.

Multiple application instances can be deployed behind a load balancer.

```
                Load Balancer
             /        |        \
            /         |         \
        API 1      API 2      API 3
               |
            PostgreSQL
```

No application-level changes are required.

---

# Stage 2 — Background Workers

Reservation expiration should move to a dedicated background worker.

Responsibilities include:

- releasing expired reservations
- notifying providers
- cleaning temporary resources

This prevents user requests from performing maintenance work.

The worker itself (currently an in-process thread on each API instance, polling every 30s) should process expired reservations **in bounded batches**, not all at once — see bottleneck #3 above for why an unbounded query becomes a self-inflicted lock storm as expired volume grows. This is a small change (add a `LIMIT` and loop) but matters more than it looks, since it's the difference between a maintenance job that scales flat and one whose worst-case cost grows with the size of the backlog it's supposed to be clearing.

---

# Stage 3 — Reliable Provider Communication

Provider communication currently happens synchronously.

As provider count grows, asynchronous communication becomes preferable.

A production system would introduce the Outbox Pattern.

```
Transaction

↓

Reservation Saved

↓

Outbox Event

↓

Background Worker

↓

Provider API
```

Benefits:

- eliminates dual-write problems
- supports retries
- isolates provider failures
- improves response time

---

# Stage 4 — Retry and Resiliency

External providers are inherently unreliable.

Retry (exponential backoff, timeout-only) and circuit breakers are already implemented per-provider (`RetryPolicy`, `CircuitBreaker`), and — after fixing `get_provider_registry` to be cached rather than reconstructed per-request — their state correctly persists for a single process's lifetime.

What's genuinely still missing at this stage:

- **Shared breaker state across instances**, once running more than one app instance — see "Per-Instance Resilience State" above. This is the actual next step, not "add circuit breakers" from scratch.
- **Wiring `CallLogger` into the provider clients.** It exists and is tested in isolation, but isn't called from `WarehouseProviderClient` or `MarketplaceSellerXProviderClient` today, so no call-level latency/outcome data is actually being recorded yet.
- **Dead-letter queues** for provider operations that exhaust retries — currently a failed provider call just surfaces as a failed reservation item; there's no queue to replay it later without the customer re-initiating checkout.

This improves availability without affecting local consistency.

---

# Stage 5 — Read Optimization

Reservation operations are write-heavy.

Other operations such as:

- product availability
- reservation lookup
- order history

are read-heavy.

Read replicas can reduce pressure on the primary database while preserving transactional integrity for writes.

---

# Database Scaling

The current design assumes a single PostgreSQL instance.

As data volume grows:

## Connection Pooling (PgBouncer)

Stage 1 states horizontal API scaling needs "no application-level changes" — that's true for the app code, but it understates a real constraint on the database side. Each app instance opens its own SQLAlchemy pool (`pool_size=5, max_overflow=10` — up to 15 connections per instance). At N=10 instances that's up to 150 possible connections, against Postgres's default `max_connections` of 100; well before that ceiling, contention for connections compounds the contention already discussed in bottleneck #1, because pessimistic locking means a connection is held for the duration of the lock, not released back to the pool the moment a query returns.

PgBouncer, running as a proxy between the app instances and Postgres, multiplexes many app-side connections onto a much smaller number of real backend connections, so adding instances no longer means a proportional increase in real DB connections. **Use transaction-mode pooling, not session or statement mode** — this codebase uses `SAVEPOINT`s (`reservation_repo.transaction()` nested transactions) and multi-statement transactions that must stay on the same backend connection for their duration; transaction mode holds the backend connection for exactly one client transaction (release on commit/rollback) and supports this correctly, where statement-mode pooling would break it.

This becomes relevant specifically at Stage 1 (once you're running more than a couple of instances) — at a single instance, 15 connections is a non-issue and adding PgBouncer ahead of that need is unnecessary operational overhead for no benefit yet.

---

## Partitioning

Reservation tables can be partitioned by creation date.

Benefits:

- faster cleanup
- smaller indexes
- improved query performance

---

## Index Optimization

Critical indexes include:

- Reservation ID
- User ID
- Reservation Status
- Expiration Time
- Product ID

These support the most common lookup patterns.

---

# Inventory Contention

Popular products naturally generate lock contention.

Potential future improvements include:

- inventory sharding
- warehouse-level inventory partitioning
- optimistic locking for low-contention products
- reservation queues for flash sales

These optimizations increase throughput while maintaining correctness.

---

# Provider Scaling

The Provider Registry allows new providers to be added without modifying reservation logic.

As provider count increases:

- each provider remains independently deployable
- provider-specific authentication stays isolated
- failures remain localized

This prevents business logic from becoming tightly coupled to provider implementations.

---

# Observability

As traffic grows, monitoring becomes essential.

Recommended metrics include:

### Reservation Metrics

- reservations created
- reservations confirmed
- reservations cancelled
- reservation failures
- expired reservations

### Inventory Metrics

- available inventory
- reserved inventory
- inventory lock wait time

### Provider Metrics

- request latency
- success rate
- timeout rate
- retry count

The data source for these already exists as scaffolding — `ProviderCallLogRepository` and the `provider_call_logs` table were built for exactly this — it's just not wired into the provider clients yet (see Database Growth / Stage 4 above). Wiring `CallLogger` in is most of the work needed to make this section actionable rather than aspirational; the metrics above are effectively a `GROUP BY provider_id, outcome` query away once that's done.

These metrics allow operational bottlenecks to be identified before they affect users.

---

# Trade-offs

Several deliberate trade-offs favor simplicity over maximum scalability.

## Pessimistic Locking

Pros:

- prevents overselling
- simple reasoning
- strong consistency

Cons:

- reduced throughput under heavy contention

Given the business domain, correctness outweighs raw performance.

---

## Synchronous Provider Calls

Pros:

- simpler implementation
- immediate consistency
- easier debugging

Cons:

- higher response latency
- provider failures affect checkout

A production system would migrate this responsibility to asynchronous processing.

---

## Modular Monolith

Pros:

- simpler deployment
- transactional consistency
- easier development

Cons:

- entire application scales together
- larger deployment units

The modular boundaries intentionally make future service extraction straightforward if required.

---

# What Breaks First?

If traffic increased significantly, components would likely reach their limits in the following order:

1. Database row locking on high-demand inventory — worsened specifically by synchronous provider calls during `confirm_reservation` extending lock hold time (see bottleneck #2)
2. Database connection exhaustion under horizontal scaling — each instance's own connection pool (up to 15 connections) multiplies with instance count against a shared `max_connections` ceiling, and compounds bottleneck #1 since locked rows hold their connection longer; this is a Stage 1 concern, not a distant one, and is what PgBouncer (Database Scaling, above) addresses
3. Slow or unavailable external providers — and, once running multiple instances, the diluted/thundering-herd effect of per-instance circuit breaker state (bottleneck #5) makes this worse before it's fixed
4. Reservation expiration processing — compounded by both the N+1 query pattern on `reservation.items` (bottleneck #6) and the unbounded batch size on `find_expired_and_lock` (bottleneck #3) as expiry volume grows; the latter turns "the worker got backed up" into "the worker locks everything at once"
5. Database storage and index growth — including `provider_call_logs` once wired in, which will grow proportionally to provider call volume, not just reservation volume
6. API server CPU and memory

Understanding this order helps prioritize optimization efforts where they provide the greatest benefit.

---

# Future Evolution

If the platform reached very large scale, the architecture could evolve toward an event-driven system:

```
Checkout

↓

Reservation Service

↓

Outbox

↓

Message Broker

↓

Inventory Workers

↓

Provider Workers

↓

Order Service
```

This architecture improves resilience, supports independent scaling of components, and isolates failures while preserving the existing domain model.

The current implementation intentionally stops short of this complexity because the assignment prioritizes correctness, clean design, and maintainability over operating a distributed system.